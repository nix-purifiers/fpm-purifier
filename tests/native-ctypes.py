# SPDX-License-Identifier: MIT
import ctypes, json, pathlib, sys

path = pathlib.Path(sys.argv[1]).resolve()
import purifier_native

assert (
    pathlib.Path(purifier_native.LIBRARIES["purifier-native-proof"]).resolve() == path
)
lib = purifier_native.load("purifier-native-proof")
lib.purifier_answer.argtypes = [ctypes.c_int]
lib.purifier_answer.restype = ctypes.c_int
assert [lib.purifier_answer(0), lib.purifier_answer(1)] == [42, 43]


class Info(ctypes.Structure):
    _fields_ = [
        ("fname", ctypes.c_char_p),
        ("base", ctypes.c_void_p),
        ("sname", ctypes.c_char_p),
        ("saddr", ctypes.c_void_p),
    ]


info = Info()
host = ctypes.CDLL(None)
assert host.dladdr(
    ctypes.cast(lib.purifier_answer, ctypes.c_void_p), ctypes.byref(info)
)
assert pathlib.Path(info.fname.decode()).resolve() == path
print(json.dumps({"values": [42, 43], "origin": info.fname.decode()}))
