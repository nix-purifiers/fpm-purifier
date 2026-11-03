"""Bind the native project and resolved graph to the selected lock."""

import json
import sys

expected = json.load(open(sys.argv[1]))
model = json.load(open(sys.argv[2]))
name = model["package-name"]
if {"name": name, "version": model["packages"][name]["version"]} != expected["project"]:
    raise ValueError("Native project identity differs from lock")
nodes = model["deps"]["dependencies"]
if set(nodes) != {name, *[n["name"] for n in expected["nodes"]]}:
    raise ValueError("Native dependency graph differs from lock")
for node in expected["nodes"]:
    actual = nodes[node["name"]]
    dependencies = actual.get("package-dep", [])
    if isinstance(dependencies, str):
        dependencies = [dependencies]
    if sorted(dependencies) != sorted(node["dependencies"]):
        raise ValueError("Native dependency edges differ from lock")
    if (
        actual["version"] != node["version"]
        or actual.get("revision") != node["revision"]
    ):
        raise ValueError("Native dependency identity differs from lock")
