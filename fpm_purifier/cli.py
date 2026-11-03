"""Lock native Fortran packages and activate normal Fortran commands."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import LOCK, load, locate, run
from .session import execute, realize


def main():
    try:
        if sys.argv[1:2] == ["--native"]:
            root, companion = locate()
            execute(root, companion, sys.argv[4:], sys.argv[2].split("=", 1)[1])
            return
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--project", type=Path)
        parser.add_argument("--lock-file", type=Path)
        sub = parser.add_subparsers(dest="command", required=True)
        p = sub.add_parser("lock")
        p.add_argument("--update", action="store_true")
        p.add_argument("--input", action="append", default=[])
        p.add_argument("--name")
        p.add_argument("--profile")
        p.add_argument("--features")
        sub.add_parser("prefetch")
        sub.add_parser("release")
        p = sub.add_parser("publish")
        p.add_argument("--repo", required=True)
        p.add_argument("--tag", required=True)
        p = sub.add_parser("exec")
        p.add_argument("args", nargs=argparse.REMAINDER)
        args = parser.parse_args()
        selected_root, selected_lock = locate()
        root = (args.project or selected_root).resolve()
        companion = (
            args.lock_file or (root / LOCK if args.project else selected_lock)
        ).resolve()
        if args.command == "lock":
            capture(
                root,
                companion,
                args.update,
                args.input,
                args.name,
                args.profile,
                args.features,
            )
        elif args.command == "exec":
            command = args.args[1:] if args.args[:1] == ["--"] else args.args
            if not command:
                raise ValueError("exec requires a command")
            execute(root, companion, command)
        else:
            data = load(root, companion)
            output = realize(
                root,
                companion,
                "release" if args.command in ("release", "publish") else "environment",
            )
            if args.command == "publish":
                gh = os.environ.get("FPM_PURIFIER_GH", "gh")
                archive = output / (
                    data["project"]["name"]
                    + "-"
                    + data["project"]["version"]
                    + ".tar.gz"
                )
                found = subprocess.run(
                    [gh, "release", "view", args.tag, "--repo", args.repo],
                    capture_output=True,
                )
                if found.returncode == 0:
                    run(
                        [
                            gh,
                            "release",
                            "upload",
                            args.tag,
                            archive,
                            "--repo",
                            args.repo,
                            "--clobber",
                        ]
                    )
                else:
                    run(
                        [
                            gh,
                            "release",
                            "create",
                            args.tag,
                            archive,
                            "--repo",
                            args.repo,
                            "--title",
                            args.tag,
                            "--notes",
                            "Native Fortran source package",
                        ]
                    )
            else:
                print(output)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"fpm-purifier: {error}", file=sys.stderr)
        sys.exit(1)
