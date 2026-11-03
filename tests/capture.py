"""Exercise native relocking, selected configurations and empty graphs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.run(
            ["nix", "build", ".#default", "--no-link", "--print-out-paths"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    / "bin/fpm-purifier"
)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "project"
    root.mkdir()
    (root / "src").mkdir()
    metadata = root / "fpm.toml"
    metadata.write_text('name="empty"\nversion="0.1.0"\nlicense="MIT"\n')
    (root / "src/empty.f90").write_text(
        "module empty\nimplicit none\nend module empty\n"
    )
    (root / "selection.txt").write_text("tracked selection\n")
    companion = Path(temporary) / "external.json"

    def call(*args):
        return subprocess.run(
            [cli, "--project", root, "--lock-file", companion, *args],
            check=True,
            capture_output=True,
            text=True,
        )

    call("lock", "--input", "selection.txt")
    empty = json.loads(companion.read_text())
    assert empty["nodes"] == empty["entries"] == []
    call("prefetch")
    before = companion.read_bytes()
    call("lock")
    assert companion.read_bytes() == before
    # A real native dependency graph/configuration change, retaining extra input.
    shutil.copy2(HERE / "examples/minimal/fpm.toml", metadata)
    shutil.copy2(
        HERE / "examples/minimal/src/purifier_proof.f90",
        root / "src/purifier_proof.f90",
    )
    (root / "src/empty.f90").unlink()
    shutil.copytree(HERE / "examples/minimal/test", root / "test")
    assert subprocess.run(
        [cli, "--project", root, "--lock-file", companion, "prefetch"],
        capture_output=True,
    ).returncode
    metadata.write_text(
        metadata.read_text()
        + '\n[[test]]\nname="unit"\nsource-dir="test"\nmain="main.f90"\n'
    )
    call("lock", "--update", "--profile", "release")
    selected = json.loads(companion.read_text())
    assert selected["configuration"]["profile"] == "release"
    assert selected["extraInputs"] == ["selection.txt"] and {
        n["name"] for n in selected["nodes"]
    } == {"jonquil", "toml-f"}
    call("prefetch")
    env = {
        **os.environ,
        "FPM_PURIFIER_PROJECT": str(root),
        "FPM_PURIFIER_LOCK": str(companion),
    }
    subprocess.run([cli.parent / "fpm", "test"], cwd=root, env=env, check=True)
    assert subprocess.run(
        [cli.parent / "fpm", "test", "--profile", "debug"],
        cwd=root,
        env=env,
        capture_output=True,
    ).returncode
    selected["nodes"][0]["version"] = "9.9.9"
    companion.write_text(json.dumps(selected))
    bad = subprocess.run(
        [cli, "--project", root, "--lock-file", companion, "prefetch"],
        capture_output=True,
    )
    assert bad.returncode and b"differs from lock" in bad.stderr
    call("lock", "--update", "--features", "")
    reset = json.loads(companion.read_text())
    assert reset["configuration"] == {"profile": "", "features": ""}
print("Native fpm capture/update/configuration and empty graph passed")
