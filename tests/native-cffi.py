# SPDX-License-Identifier: MIT
import json, pathlib, sys
from cffi import FFI

f = FFI()
f.cdef("""int purifier_answer(int);
typedef struct { const char *dli_fname; void *dli_fbase; const char *dli_sname; void *dli_saddr; } Dl_info;
int dladdr(void *, Dl_info *);""")
p = pathlib.Path(sys.argv[1]).resolve()
lib = f.dlopen(str(p))
host = f.dlopen(None)
assert [lib.purifier_answer(0), lib.purifier_answer(1)] == [42, 43]
i = f.new("Dl_info *")
assert host.dladdr(f.cast("void *", lib.purifier_answer), i)
origin = f.string(i.dli_fname).decode()
assert pathlib.Path(origin).resolve() == p
print(json.dumps({"values": [42, 43], "origin": origin}))
