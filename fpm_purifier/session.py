"""Use compiled Nix dependencies in ordinary native application builds."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from .common import HERE, STATE, clean_env, load, native, run


def realize(root, companion, target="environment", flags=()):
    state = root / STATE
    state.mkdir(exist_ok=True)
    key = hashlib.sha256(json.dumps(list(flags)).encode()).hexdigest()[:16]
    profile = state / (target + "-" + key + ".json")
    run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            HERE / "nix/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "target",
            target,
            "--arg",
            "profile",
            "true",
            "--argstr",
            "sdk",
            os.environ["FPM_PURIFIER_SDK"],
            "--argstr",
            "flags",
            json.dumps(list(flags)),
            "--out-link",
            profile,
        ],
        stdout=sys.stderr,
    )
    return Path(json.loads(profile.read_text())["output"])


def execute(root, companion, args, tool=None):
    if not companion.exists():
        if os.environ.get("FPM_PURIFIER_LOCK"):
            raise ValueError("Selected lockfile does not exist")
        print(
            "warning: no fpm-purifier lockfile; using ordinary impure resolution",
            file=sys.stderr,
        )
        command = [native(tool), *args] if tool else args
        os.execvpe(str(command[0]), list(map(str, command)), os.environ.copy())
    data = load(root, companion)
    selected = {k: v for k, v in data["configuration"].items() if v}
    flags = []
    if tool:
        if args[:1] == ["update"]:
            raise ValueError(
                "Use fpm-purifier lock --update to change dependency selection"
            )
        index = 1
        while index < len(args):
            option = args[index]
            attached = None
            if option.startswith("--") and "=" in option:
                option, attached = option.split("=", 1)
            if option == "--":
                break
            if option in (
                "--compiler",
                "--c-compiler",
                "--cxx-compiler",
                "--archiver",
                "--build-dir",
                "--config-file",
            ):
                raise ValueError(
                    "Locked sessions use the pinned compiler and private build directory"
                )
            if option in (
                "--profile",
                "--features",
                "--flag",
                "--c-flag",
                "--cxx-flag",
                "--link-flag",
            ):
                if attached is None and index + 1 >= len(args):
                    raise ValueError("Missing value for " + option)
                value = attached if attached is not None else args[index + 1]
                if option in ("--profile", "--features"):
                    if selected.get(option[2:]) != value:
                        raise ValueError(
                            "This lock selects another configuration; run lock --update with the requested --profile or --features"
                        )
                else:
                    flags.extend([option, value])
                index += 1 if attached is not None else 2
            else:
                index += 1
        if args[:1] in (["build"], ["test"], ["run"], ["install"]):
            for key, value in selected.items():
                if not any(arg.split("=", 1)[0] == "--" + key for arg in args):
                    split = args.index("--") if "--" in args else len(args)
                    args = [*args[:split], "--" + key, value, *args[split:]]
    environment = realize(root, companion, flags=flags)
    signature = hashlib.sha256(
        (companion.read_text() + str(environment)).encode()
    ).hexdigest()
    state = root / STATE / "session" / signature
    env = clean_env(state)
    build = state / "build"
    build.mkdir(exist_ok=True)
    shutil.copyfile(environment / "build/cache.toml", build / "cache.toml")
    env.update(
        FPM_FC="gfortran",
        FPM_CC="gcc",
        FPM_CXX="g++",
        FPM_AR="ar",
        FPM_BUILD_DIR=str(build),
        FPM_PURIFIER_FROZEN="1",
        FPM_PURIFIER_OBJECT_PREFIX=str(environment / "build/gfortran"),
        FPM_PURIFIER_PROJECT=str(root),
        FPM_PURIFIER_LOCK=str(companion),
    )
    env["PATH"] = os.environ["FPM_PURIFIER_SDK"] + "/bin:" + env["PATH"]
    if tool:
        command = [native(tool), *args]
    else:
        command = args
    if tool:
        os.chdir(root)
    os.execvpe(str(command[0]), list(map(str, command)), env)
