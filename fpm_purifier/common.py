"""SDK identity and project metadata freshness."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

LOCK = "fpm-purifier.lock.json"
STATE = Path(".fpm-purifier")
HERE = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run([str(value) for value in args], check=True, **kwargs)


def native(tool):
    return os.environ["FPM_PURIFIER_NATIVE_" + tool.upper().replace("-", "_")]


def versions():
    return {
        key.lower(): os.environ["FPM_PURIFIER_" + key + "_VERSION"]
        for key in ("SDK", "FPM", "GFORTRAN", "GCC")
    }


def clean_env(state):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("FPM_") or key in (
            "FC",
            "CC",
            "AR",
            "CXX",
            "FFLAGS",
            "CFLAGS",
            "CXXFLAGS",
            "LDFLAGS",
            "CPATH",
            "LIBRARY_PATH",
            "LD_LIBRARY_PATH",
            "PKG_CONFIG_PATH",
        ):
            env.pop(key, None)
    for key, leaf in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ):
        location = state / leaf
        location.mkdir(parents=True, exist_ok=True)
        env[key] = str(location)
    env["OSTYPE"] = "linux-gnu"
    return env


def inputs(root, extra=()):
    names = sorted(set(["fpm.toml", *extra]))
    result = {}
    for name in names:
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.resolve() != path
            or not path.is_file()
        ):
            raise ValueError("Inputs must be regular files inside the project: " + name)
        blob = path.read_bytes()
        result[name] = {
            "content": blob.decode(),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
    return result


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "fpm":
        raise ValueError("Invalid fpm-purifier lock")
    if data.get("toolVersions") != versions():
        raise ValueError("Fortran SDK changed; run fpm-purifier lock --update")
    if data["inputs"] != inputs(root, data.get("extraInputs", [])):
        raise ValueError("Fortran metadata changed; run fpm-purifier lock --update")
    return data


def locate():
    selected = os.environ.get("FPM_PURIFIER_LOCK")
    if selected:
        companion = Path(selected).resolve()
        root = Path(os.environ.get("FPM_PURIFIER_PROJECT", companion.parent)).resolve()
        return root, companion
    root = next(
        (path for path in (Path.cwd(), *Path.cwd().parents) if (path / LOCK).exists()),
        Path.cwd(),
    )
    return root, root / LOCK
