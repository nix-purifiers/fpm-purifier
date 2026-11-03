"""Project the native fpm cache format onto immutable fetched sources."""

import json
from pathlib import Path
import sys

manifest, sources, output = map(Path, sys.argv[1:])
data = json.loads(manifest.read_text())
result = (
    "["
    + json.dumps(data["project"]["name"])
    + "]\nversion="
    + json.dumps(data["project"]["version"])
    + '\nproj-dir="."\n'
)
for node in data["nodes"]:
    fields = {
        "version": node["version"],
        "proj-dir": str(sources / node["entry"]),
        "git": node["url"],
        "rev": node["revision"],
    }
    if node["requested"] is not None:
        fields["obj"] = node["requested"]
    result += (
        "\n["
        + json.dumps(node["name"])
        + "]\n"
        + "".join(k + "=" + json.dumps(v) + "\n" for k, v in fields.items())
    )
output.write_text(result)
