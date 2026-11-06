# SPDX-License-Identifier: MIT
"""Validate the native root DSO before install and preserve its installed bytes."""

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

mode, output, nm, receipt_path = sys.argv[1:]
spec = json.loads(os.environ["nativeSpec"])
prefix = Path(output).absolute()
if prefix.is_symlink():
    raise ValueError("FPM native output root must not be a symlink")
name = spec["libraryFile"]
if Path(name).name != name or name in (".", ".."):
    raise ValueError("FPM native artifact name must not escape output")


def shared_elf(path):
    data = path.read_bytes()
    machine = {"x86_64-linux": 62, "aarch64-linux": 183}.get(spec["system"])
    if (
        machine is None
        or len(data) < 64
        or data[:6] != b"\x7fELF\x02\x01"
        or struct.unpack_from("<HH", data, 16) != (3, machine)
    ):
        raise ValueError("FPM native artifact must be a target ELF64 shared library")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    entsize, count = struct.unpack_from("<HH", data, 54)
    if (
        entsize < 56
        or count == 0
        or count == 65535
        or phoff + entsize * count > len(data)
    ):
        raise ValueError("FPM native artifact has invalid ELF program headers")
    for i in range(count):
        offset = phoff + entsize * i
        kind = struct.unpack_from("<I", data, offset)[0]
        if kind == 3:
            raise ValueError("FPM native artifact must not be a PIE executable")
        if kind == 2:
            start = struct.unpack_from("<Q", data, offset + 8)[0]
            size = struct.unpack_from("<Q", data, offset + 32)[0]
            if start + size > len(data) or size % 16:
                raise ValueError("FPM native artifact has invalid ELF dynamic entries")
            for position in range(start, start + size, 16):
                tag, value = struct.unpack_from("<qQ", data, position)
                if tag == 0x6FFFFFFB and value & 0x08000000:
                    raise ValueError("FPM native artifact must not be a PIE executable")
    return hashlib.sha256(data).hexdigest()


def exports(path):
    names = {
        line.split()[-1].split("@")[0]
        for line in subprocess.check_output(
            [nm, "-D", "--defined-only", str(path)], text=True
        ).splitlines()
        if line.split()
    }
    missing = set(spec["products"][spec["rootName"]]["exports"]) - names
    if missing:
        raise ValueError(
            "FPM declared C exports are not defined by native root: "
            + ", ".join(sorted(missing))
        )


build = prefix / "build"
candidates = list(build.rglob(name))
if len(candidates) != 1:
    raise ValueError("FPM requires exactly one native-built root shared artifact")
artifact = candidates[0].resolve(strict=True)
if not artifact.is_relative_to(build) or not artifact.is_file():
    raise ValueError("FPM native artifact escapes build output")
if mode == "preflight":
    digest = shared_elf(artifact)
    exports(artifact)
    Path(receipt_path).write_text(
        json.dumps({"artifact": str(artifact), "sha256": digest})
    )
elif mode == "installed":
    receipt = json.loads(Path(receipt_path).read_text())
    installed = (prefix / "lib" / name).resolve(strict=True)
    if not installed.is_relative_to(prefix) or not installed.is_file():
        raise ValueError("FPM installed native artifact escapes producer")
    if (
        str(artifact) != receipt["artifact"]
        or shared_elf(artifact) != receipt["sha256"]
    ):
        raise ValueError("FPM native artifact changed during installation")
    if shared_elf(installed) != receipt["sha256"]:
        raise ValueError("FPM installed native bytes differ from native build")
    exports(installed)
else:
    raise ValueError("unknown FPM native artifact operation")
