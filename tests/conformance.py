"""Exercise native fpm while dependencies stay compiled in the Nix store."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def build(name):
    return Path(
        run(
            ["nix", "build", ".#" + name, "--no-link", "--print-out-paths"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    )


cli, sdk = build("default"), build("sdk")
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    root = directory / "renamed-project"
    shutil.copytree(
        HERE / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".fpm-purifier", "build"),
    )
    helper = cli / "bin/fpm-purifier"
    env = {
        **os.environ,
        "PATH": str(cli / "bin") + ":" + os.environ["PATH"],
        "FPM_BUILD_DIR": "/poison/build",
        "FPM_FC": "/poison/compiler",
        "FPM_FFLAGS": "-invalid-poison",
        "FPM_PURIFIER_OBJECT_PREFIX": "/poison/objects",
    }
    run([helper, "--project", root, "prefetch"])
    native = run(
        [cli / "bin/fpm", "test", "--verbose"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert "42" in native.stdout
    assert " -c /nix/store/" not in native.stdout + native.stderr
    assert "-I/nix/store/" in native.stdout + native.stderr
    (root / "nested").mkdir()
    run([cli / "bin/fpm", "test"], cwd=root / "nested", env=env)
    # Additional compiler flags select another immutable dependency build.
    optimized = run(
        [cli / "bin/fpm", "test", "--flag=-O1", "--verbose"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (
        "42" in optimized.stdout
        and " -c /nix/store/" not in optimized.stdout + optimized.stderr
    )
    source = root / "src/purifier_proof.f90"
    original_source = source.read_text()
    source.write_text(original_source.replace('"answer", 42', '"answer", 43'))
    negative = subprocess.run(
        [cli / "bin/fpm", "test", "--verbose"], cwd=root, env=env, capture_output=True
    )
    assert negative.returncode
    source.write_text(original_source)
    restored = run(
        [cli / "bin/fpm", "test", "--verbose"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (
        "42" in restored.stdout
        and " -c /nix/store/" not in restored.stdout + restored.stderr
    )
    companion = root / "fpm-purifier.lock.json"
    original_lock = companion.read_bytes()
    run([helper, "--project", root, "lock"])
    assert companion.read_bytes() == original_lock
    profiles = list((root / ".fpm-purifier").glob("environment-*.json"))
    assert profiles
    for profile in profiles:
        data = json.loads(profile.read_text())
        refs = run(
            ["nix-store", "--query", "--references", profile],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert data["sdk"] in refs and data["output"] in refs
    # Native model exports provide source locations for editor/compiler tooling.
    model = root / "model.json"
    run(
        [cli / "bin/fpm", "build", "--list", "--dump", model],
        cwd=root,
        env=env,
        capture_output=True,
    )
    exported = json.loads(model.read_text())
    dependency = exported["packages"]["jonquil"]["sources"]
    assert all(
        item["file-name"].startswith("/nix/store/") for item in dependency.values()
    )
    model.unlink()
    release = Path(
        run(
            [helper, "--project", root, "release"], capture_output=True, text=True
        ).stdout.strip()
    )
    archive = release / "purifier-proof-0.1.0.tar.gz"
    consumer = directory / "consumer"
    consumer.mkdir()
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("FPM_")}
    clean_env["PATH"] = str(sdk / "bin") + ":" + clean_env["PATH"]
    run([sdk / "bin/tar", "-xzf", archive, "-C", consumer], env=clean_env)
    consumed = run(
        [sdk / "bin/fpm", "test"],
        cwd=consumer,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    assert "42" in consumed.stdout
    fake = directory / "gh"
    log = directory / "gh.jsonl"
    uploaded = directory / "uploaded.tar.gz"
    fake.write_text(
        '#!/usr/bin/env python3\nimport json,os,sys,shutil\nwith open(os.environ["GH_TEST_LOG"],"a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\nif sys.argv[1:3]==["release","view"]:sys.exit(1 if os.environ.get("GH_TEST_CREATE") else 0)\nfor arg in sys.argv[3:]:\n if arg.endswith(".tar.gz"):shutil.copyfile(arg,os.environ["GH_TEST_BYTES"])\n'
    )
    fake.chmod(0o755)
    for create in (True, False):
        publish_env = {
            **os.environ,
            "FPM_PURIFIER_GH": str(fake),
            "GH_TEST_LOG": str(log),
            "GH_TEST_BYTES": str(uploaded),
        }
        if create:
            publish_env["GH_TEST_CREATE"] = "1"
        run(
            [
                helper,
                "--project",
                root,
                "publish",
                "--repo",
                "example/project",
                "--tag",
                "v0.1.0",
            ],
            env=publish_env,
        )
        assert uploaded.read_bytes() == archive.read_bytes()
    assert [json.loads(line)[1] for line in log.read_text().splitlines()] == [
        "view",
        "create",
        "view",
        "upload",
    ]
    data = json.loads(original_lock)
    data["project"]["version"] = "9.9.9"
    companion.write_text(json.dumps(data))
    assert subprocess.run(
        [helper, "--project", root, "release"], capture_output=True
    ).returncode
    companion.write_bytes(original_lock)
    external = directory / "external.json"
    companion.rename(external)
    external_env = {
        **env,
        "FPM_PURIFIER_PROJECT": str(root),
        "FPM_PURIFIER_LOCK": str(external),
    }
    run([cli / "bin/fpm", "test"], cwd=root, env=external_env)
    external.rename(companion)
    metadata = root / "fpm.toml"
    metadata.write_text(metadata.read_text() + "\n# metadata changed\n")
    stale = subprocess.run(
        [cli / "bin/fpm", "test"], cwd=root, env=env, capture_output=True
    )
    assert stale.returncode and b"metadata changed" in stale.stderr
    plain = directory / "plain"
    plain.mkdir()
    fallback = subprocess.run(
        [
            helper,
            "exec",
            "--",
            "python3",
            "-c",
            'import sys;sys.stdout.write(sys.stdin.read());sys.stderr.write("native-stderr\\n");sys.exit(7)',
        ],
        cwd=plain,
        input=b"ordinary-input\n",
        capture_output=True,
    )
    assert fallback.returncode == 7 and fallback.stdout == b"ordinary-input\n"
    assert (
        b"ordinary impure resolution" in fallback.stderr
        and b"native-stderr" in fallback.stderr
    )
    ordinary = run(
        [cli / "bin/fpm", "--version"], cwd=plain, capture_output=True, text=True
    )
    assert (
        "0.13.0" in ordinary.stdout and "ordinary impure resolution" in ordinary.stderr
    )
print("Native fpm conformance passed")
