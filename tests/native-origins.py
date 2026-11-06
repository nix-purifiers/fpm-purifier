# SPDX-License-Identifier: MIT
import ctypes, json, pathlib, subprocess, sys

prefix = pathlib.Path(sys.argv[1]).resolve()
runtime = pathlib.Path(sys.argv[2]).resolve()
root = ctypes.CDLL(str(prefix / "lib/libpurifier-native-proof.so"))


class Info(ctypes.Structure):
    _fields_ = [
        ("fname", ctypes.c_char_p),
        ("base", ctypes.c_void_p),
        ("sname", ctypes.c_char_p),
        ("saddr", ctypes.c_void_p),
    ]


host = ctypes.CDLL(None)


def origin(symbol):
    i = Info()
    assert host.dladdr(
        ctypes.cast(getattr(root, symbol), ctypes.c_void_p), ctypes.byref(i)
    )
    return pathlib.Path(i.fname.decode()).resolve()


def names(library, defined):
    return [
        line.split()[-1].split("@")[0]
        for line in subprocess.check_output(
            [
                "nm",
                "-D",
                "--defined-only" if defined else "--undefined-only",
                str(library),
            ],
            text=True,
        ).splitlines()
        if line.split()
    ]


rows = []
for library, marker in [("libjonquil.so", "__jonquil"), ("libtoml-f.so", "__tomlf")]:
    expected = (prefix / "lib" / library).resolve()
    symbol = next(n for n in names(expected, True) if n.startswith(marker))
    actual = origin(symbol)
    assert actual == expected, (actual, expected)
    rows.append(
        {"kind": "installed-dependency", "symbol": symbol, "origin": str(actual)}
    )
symbol = next(
    n for n in names(prefix / "lib/libjonquil.so", False) if n.startswith("_gfortran_")
)
actual = origin(symbol)
assert actual.is_relative_to(runtime / "lib"), (actual, runtime)
rows.append({"kind": "compiler-runtime", "symbol": symbol, "origin": str(actual)})
print(json.dumps(rows))
