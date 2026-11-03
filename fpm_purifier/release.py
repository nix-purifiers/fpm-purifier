"""Build a deterministic source bundle for native fpm consumers."""

import gzip
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib

manifest, source, output, tool = map(Path, sys.argv[1:])
data = json.loads(manifest.read_text())
metadata = tomllib.loads((source / "fpm.toml").read_text())
version = subprocess.check_output(
    [tool, "publish", "--show-package-version"], cwd=source, text=True
).strip()
if {"name": metadata["name"], "version": version} != data["project"]:
    raise ValueError("Native project identity differs from lock")
archive = output / (data["project"]["name"] + "-" + version + ".tar.gz")
with (
    archive.open("wb") as raw,
    gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed,
    tarfile.open(fileobj=compressed, mode="w") as target,
):
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Use regular source files in release bundles")
        info = target.gettarinfo(str(path), arcname=str(path.relative_to(source)))
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 1
        if path.is_file():
            with path.open("rb") as stream:
                target.addfile(info, stream)
        elif path.is_dir():
            target.addfile(info)
