"""Capture the native build model and hash its selected Git trees."""

import json
from pathlib import Path
import re
import shutil
import tempfile

from .common import STATE, clean_env, inputs, load, native, run, versions


def capture(
    root, companion, update=False, extra=(), name=None, profile=None, features=None
):
    old = json.loads(companion.read_text()) if companion.exists() else {}
    if companion.exists() and not update:
        current = load(root, companion)
        if extra and sorted(set(extra)) != current["extraInputs"]:
            raise ValueError("Changed --input requires lock --update")
        if profile is not None or features is not None:
            raise ValueError(
                "Changing the selected configuration requires lock --update"
            )
        if name and name != current["project"]["name"]:
            raise ValueError("--name differs from the native project name")
        return
    extra = sorted(set(extra or old.get("extraInputs", [])))
    configuration = old.get("configuration", {})
    selected_profile = (
        profile if profile is not None else configuration.get("profile", "")
    )
    selected_features = (
        features if features is not None else configuration.get("features", "")
    )
    if profile is not None and features is None:
        selected_features = ""
    if features is not None and profile is None:
        selected_profile = ""
    if selected_profile and selected_features:
        raise ValueError("Select either --profile or --features")
    configuration = {"profile": selected_profile, "features": selected_features}
    selection = []
    for key in ("profile", "features"):
        if configuration[key]:
            selection += ["--" + key, configuration[key]]
    recorded = inputs(root, extra)
    state = root / STATE
    state.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capture-", dir=state) as temporary:
        work = Path(temporary).resolve()
        env = clean_env(work)
        env["FPM_BUILD_DIR"] = str(work / "build")
        model = work / "model.json"
        run(
            [
                native("fpm"),
                "build",
                "--tests",
                "--show-model",
                "--dump",
                model,
                *selection,
            ],
            cwd=root,
            env=env,
            capture_output=True,
        )
        if not model.is_file():
            raise ValueError("Native fpm did not export its build model")
        plan = json.loads(model.read_text())
        project_name = plan["package-name"]
        project = {
            "name": project_name,
            "version": plan["packages"][project_name]["version"],
        }
        if name and name != project_name:
            raise ValueError("--name differs from the native project name")
        entries, nodes = [], []
        for package, node in plan["deps"]["dependencies"].items():
            if package == project_name:
                continue
            if (
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", package)
                or "git" not in node
            ):
                raise ValueError(
                    "This integration currently supports Git dependencies; unsupported package "
                    + package
                )
            source = Path(node["proj-dir"])
            if not source.is_absolute():
                source = root / source
            fetched = json.loads(
                run(
                    [
                        "nix-prefetch-git",
                        "--url",
                        node["git"]["url"],
                        "--rev",
                        node["revision"],
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            if (
                fetched["rev"] != node["revision"]
                or fetched["fetchSubmodules"]
                or fetched["leaveDotGit"]
            ):
                raise ValueError("Unexpected Git prefetch result")
            normalized = work / ("source-" + package)
            shutil.copytree(
                source, normalized, symlinks=True, ignore=shutil.ignore_patterns(".git")
            )
            actual = run(
                ["nix", "hash", "path", normalized],
                env=env,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if actual != fetched["hash"]:
                raise ValueError(
                    "Native fpm source differs from the pinned Git tree: " + package
                )
            path = "git/" + package
            entries.append(
                {
                    "path": path,
                    "hash": fetched["hash"],
                    "git": {
                        "url": node["git"]["url"],
                        "rev": node["revision"],
                        "submodules": False,
                        "leaveDotGit": False,
                        "commitObject": None,
                    },
                }
            )
            depends = node.get("package-dep", [])
            if isinstance(depends, str):
                depends = [depends]
            nodes.append(
                {
                    "name": package,
                    "version": node["version"],
                    "entry": path,
                    "url": node["git"]["url"],
                    "requested": node["git"].get("object"),
                    "revision": node["revision"],
                    "dependencies": depends,
                }
            )
        data = {
            "version": 1,
            "purifier": "fpm",
            "toolVersions": versions(),
            "project": project,
            "configuration": configuration,
            "inputs": recorded,
            "extraInputs": extra,
            "nodes": sorted(nodes, key=lambda n: n["name"]),
            "entries": sorted(entries, key=lambda e: e["path"]),
        }
    companion.parent.mkdir(parents=True, exist_ok=True)
    pending = companion.with_name(companion.name + ".tmp")
    pending.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    pending.replace(companion)
