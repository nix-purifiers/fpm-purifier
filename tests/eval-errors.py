"""Check the lock protocol without allowing import-from-derivation."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    source = Path(temporary) / "project"
    shutil.copytree(
        HERE / "examples/minimal",
        source,
        ignore=shutil.ignore_patterns(".fpm-purifier", "build"),
    )
    companion = source / "fpm-purifier.lock.json"
    original = json.loads(companion.read_text())

    def problems():
        expression = f"let f=builtins.getFlake {json.dumps(str(HERE))};lock=f.lib.fpm-purifier.readLock {{src=/. + {json.dumps(str(source))};}};in {{inherit(lock)problems outputs;fetches=map(e: e.path)lock.entries;}}"
        return json.loads(
            subprocess.run(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )

    valid = problems()
    assert valid["problems"] == [] and valid["outputs"]["packages"] == [
        "default",
        "environment",
        "project",
    ]
    companion.unlink()
    assert problems()["problems"]
    for mutate in [
        lambda d: d.update(purifier="other"),
        lambda d: d["nodes"][0].update(revision="invalid"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d["configuration"].update(profile="release", features="unknown"),
        lambda d: d["project"].update(version="9.9.9"),
        lambda d: d["toolVersions"].update(sdk=None),
    ]:
        data = json.loads(json.dumps(original))
        mutate(data)
        companion.write_text(json.dumps(data))
        assert problems()["problems"]
    companion.write_text(json.dumps(original))
    (source / "fpm.toml").write_text("# stale\n")
    assert problems()["problems"]
print("Fortran lock validation passed without IFD")
