# SPDX-License-Identifier: MIT
"""Capture the actual runner graph and exercise installed native projections."""

import copy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parents[1]
PRODUCT = {
    "abi": "c",
    "exports": ["purifier_answer"],
    "runtime": {"kind": "gfortran", "lifecycle": "caller-managed"},
}
PRODUCTS = {"purifier-native-proof": PRODUCT}


def run(args, success=True, timeout=900, env=None):
    p = subprocess.run(
        list(map(str, args)), text=True, capture_output=True, timeout=timeout, env=env
    )
    if success and p.returncode:
        raise AssertionError(p.stdout + p.stderr)
    return p


with tempfile.TemporaryDirectory(prefix="fpm-native-projections-") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(HERE / "tests/fixtures/native", root)
    cli = (
        Path(
            run(
                [
                    "nix",
                    "build",
                    "path:" + str(HERE) + "#cli",
                    "--no-link",
                    "--print-out-paths",
                ]
            ).stdout.strip()
        )
        / "bin/fpm-purifier"
    )
    env = dict(os.environ, HOME=str(temp / "home"))
    Path(env["HOME"]).mkdir()

    def capture():
        run([cli, "--project", root, "lock"], env=env)
        return json.loads((root / "fpm-purifier.lock.json").read_text())

    lock = capture()
    assert {n["name"] for n in lock["nodes"]} == {"jonquil", "toml-f"}

    def expression(
        products=PRODUCTS, extra="", result="built.packages.project.drvPath"
    ):
        return f"""
let
 f=builtins.getFlake {json.dumps('path:'+str(HERE))};
 pkgs=import f.inputs.nixpkgs {{ system=builtins.currentSystem; overlays=[ f.overlays.default ]; }};
 built=pkgs.fpm-purifier.buildFortranProject {{ src={root}; nativeProducts=builtins.fromJSON {json.dumps(json.dumps(products))}; {extra} }};
in {result}
"""

    def evaluate(products=PRODUCTS):
        return run(
            [
                "nix",
                "eval",
                "--impure",
                "--json",
                "--option",
                "allow-import-from-derivation",
                "false",
                "--expr",
                expression(products),
            ],
            success=False,
        )

    def build(
        extra="", products=PRODUCTS, success=True, result="built.packages.project"
    ):
        return run(
            [
                "nix",
                "build",
                "--impure",
                "--no-link",
                "--print-out-paths",
                "--expr",
                expression(products, extra, result),
            ],
            success=success,
            timeout=1800,
        )

    assert evaluate().returncode == 0
    empty = run(
        [
            "nix",
            "eval",
            "--impure",
            "--json",
            "--expr",
            expression({}, result="built.projections"),
        ]
    )
    assert json.loads(empty.stdout) == {}
    consumer = f"import {HERE}/tests/native-consumer.nix {{ inherit pkgs built; product=builtins.fromJSON {json.dumps(json.dumps(PRODUCT))}; }}"
    output = build(result=consumer).stdout.strip()
    catalog = json.loads((Path(output) / "catalog.json").read_text())
    system = run(
        ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"]
    ).stdout.strip()
    assert catalog["system"] == system
    rejected = 0
    invalid = []
    for key, value in [
        ("abi", "fortran"),
        ("exports", []),
        ("exports", ["purifier_answer", "purifier_answer"]),
        ("exports", ["../escape"]),
        ("exports", [123]),
        ("runtime", {}),
    ]:
        p = copy.deepcopy(PRODUCT)
        p[key] = value
        invalid.append({"purifier-native-proof": p})
    for key, value in [("kind", "unknown"), ("lifecycle", "automatic")]:
        p = copy.deepcopy(PRODUCT)
        p["runtime"][key] = value
        invalid.append({"purifier-native-proof": p})
    invalid += [{"../escape": PRODUCT}, PRODUCTS | {"duplicate-root": PRODUCT}]
    for products in invalid:
        bad = evaluate(products)
        assert bad.returncode and "nativeProducts requires" in bad.stderr, bad.stderr
        rejected += 1
    p = copy.deepcopy(PRODUCT)
    p["exports"] = ["missing_native_export"]
    bad = build(
        'installCommand = "echo UNEXPECTED_INSTALL >&2; exit 99";',
        {"purifier-native-proof": p},
        False,
    )
    assert (
        bad.returncode
        and "exports are not defined" in bad.stderr
        and "UNEXPECTED_INSTALL" not in bad.stderr
    ), bad.stderr
    rejected += 1
    base = 'fpm build\npurifier_native_artifact=$(find "$out/build" -name libpurifier-native-proof.so -type f -print -quit)\n'
    wrong_machine = shlex.quote(
        'from pathlib import Path;import os;p=Path(os.environ["purifier_native_artifact"]);d=bytearray(p.read_bytes());d[18:20]=bytes(2);p.write_bytes(d)'
    )
    wrong_class = shlex.quote(
        'from pathlib import Path;import os;p=Path(os.environ["purifier_native_artifact"]);d=bytearray(p.read_bytes());d[4]=1;p.write_bytes(d)'
    )
    hide_interpreter = shlex.quote(
        'from pathlib import Path;import os,struct;p=Path(os.environ["purifier_native_artifact"]);d=bytearray(p.read_bytes());off=struct.unpack_from("<Q",d,32)[0];size,count=struct.unpack_from("<HH",d,54);[(struct.pack_into("<I",d,off+i*size,4)) for i in range(count) if struct.unpack_from("<I",d,off+i*size)[0]==3];p.write_bytes(d)'
    )
    for command, expected in [
        ('rm "$purifier_native_artifact"', "exactly one native-built"),
        (
            'mkdir -p "$out/build/decoy"; cp "$purifier_native_artifact" "$out/build/decoy/libpurifier-native-proof.so"',
            "exactly one native-built",
        ),
        (
            'mv "$purifier_native_artifact" "$TMPDIR/alien.so"; ln -s "$TMPDIR/alien.so" "$purifier_native_artifact"',
            "escapes build output",
        ),
        (
            "export purifier_native_artifact; python3 -c " + wrong_machine,
            "target ELF64 shared library",
        ),
        (
            "export purifier_native_artifact; python3 -c " + wrong_class,
            "target ELF64 shared library",
        ),
        (
            "gcc -fPIE -pie -x c -o \"$purifier_native_artifact\" - <<'C'\nint main(void){return 0;}\nC",
            "PIE executable",
        ),
    ]:
        extra = (
            "buildCommand = builtins.fromJSON "
            + json.dumps(json.dumps(base + command))
            + ";"
        )
        bad = build(extra, success=False)
        assert bad.returncode and expected in bad.stderr, bad.stderr
        rejected += 1
    pie = (
        "gcc -fPIE -pie -x c -o \"$purifier_native_artifact\" - <<'C'\nint main(void){return 0;}\nC\nexport purifier_native_artifact; python3 -c "
        + hide_interpreter
    )
    extra = (
        "buildCommand = builtins.fromJSON " + json.dumps(json.dumps(base + pie)) + ";"
    )
    bad = build(extra, success=False)
    assert bad.returncode and "PIE executable" in bad.stderr, bad.stderr
    rejected += 1
    install = 'fpm install --prefix "$out" --no-rebuild\n'
    for command, expected in [
        ('rm "$out/lib/libpurifier-native-proof.so"', "FileNotFoundError"),
        (
            'rm "$out/lib/libpurifier-native-proof.so"; ln -s /etc/hosts "$out/lib/libpurifier-native-proof.so"',
            "escapes producer",
        ),
        (
            'cp "$out/lib/libjonquil.so" "$out/lib/libpurifier-native-proof.so"',
            "bytes differ",
        ),
        (
            'mv "$out" "$TMPDIR/relocated"; ln -s "$TMPDIR/relocated" "$out"',
            "root must not be a symlink",
        ),
        (
            'find "$out/build" -name libpurifier-native-proof.so -type f -exec sh -c \'printf "\\n" >> "$1"\' _ {} \\;',
            "changed during installation",
        ),
    ]:
        extra = (
            "installCommand = builtins.fromJSON "
            + json.dumps(json.dumps(install + command))
            + ";"
        )
        bad = build(extra, success=False)
        assert bad.returncode and expected in bad.stderr, bad.stderr
        rejected += 1
    # Same native shared target with no declared C binding is not a C API.
    edit = 'from pathlib import Path;p=Path("src/library.f90");s=p.read_text();old=\' bind(C, name="purifier_answer")\';assert s.count(old)==1;p.write_text(s.replace(old,""))'
    extra = (
        "buildCommand = builtins.fromJSON "
        + json.dumps(json.dumps("python3 -c " + shlex.quote(edit) + "\nfpm build"))
        + ";"
    )
    bad = build(extra, success=False)
    assert bad.returncode and "exports are not defined" in bad.stderr, bad.stderr
    rejected += 1
    # Recapture an actual native static target; never fabricate a shared artifact.
    recipe = root / "fpm.toml"
    recipe.write_text(
        recipe.read_text().replace('type = "shared"', 'type = "monolithic"')
    )
    (root / "fpm-purifier.lock.json").unlink()
    capture()
    bad = build(success=False)
    assert bad.returncode and "exactly one native-built" in bad.stderr, bad.stderr
    rejected += 1
    print(
        json.dumps(
            {
                "system": system,
                "nativeCapture": True,
                "consumerOutput": output,
                "rejected": rejected,
            }
        )
    )
