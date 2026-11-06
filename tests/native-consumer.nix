{
  pkgs,
  built,
  product,
}:
let
  view = built.projections.native;
in
pkgs.runCommand "fpm-native-projection-consumers"
  {
    nativeBuildInputs = [
      pkgs.gcc
      (pkgs.python3.withPackages (ps: [ ps.cffi ]))
      pkgs.jdk25
      pkgs.binutils
      pkgs.coreutils
    ];
  }
  ''
     set -euo pipefail
     mkdir -p "$out"
     export PYTHONPATH=${view}
     python3 - <<'PY'
    import json
    from pathlib import Path
    c=json.loads(Path('${view}/catalog.json').read_text());t=c['targets']['purifier-native-proof']
    assert t['abi']=='c' and t['exports']==['purifier_answer']
    assert t['runtime']==json.loads('${builtins.toJSON product.runtime}')
    assert t['compiler']['runtimePath']=='${pkgs.gfortran.cc.lib}'
    assert c['prefix']=='${built.packages.project}' and c['includeDirectories']==[]
    assert Path(t['nativeModel'])==Path(c['prefix'])/'model.json'
    assert set(c['libraries'])=={'purifier-native-proof'}
    Path('library-path').write_text(c['libraries']['purifier-native-proof'])
    PY
     lib=$(cat library-path)
     gcc ${./native-consumer.c} -ldl -o c-consumer
     timeout 25s ./c-consumer "$lib" > "$out/c.txt" 2> "$out/c.stderr"
     timeout 25s python3 ${./native-ctypes.py} "$lib" > "$out/ctypes.json" 2> "$out/ctypes.stderr"
     timeout 25s python3 ${./native-cffi.py} "$lib" > "$out/cffi.json" 2> "$out/cffi.stderr"
     timeout 25s python3 ${./native-origins.py} ${built.packages.project} ${pkgs.gfortran.cc.lib} > "$out/dependency-origins.json"
     cp ${./NativeConsumer.java} NativeConsumer.java
     javac NativeConsumer.java
     timeout 25s java --enable-native-access=ALL-UNNAMED @${view}/java.args NativeConsumer "$lib" > "$out/java.txt" 2> "$out/java.stderr"
     for name in c ctypes cffi java; do test ! -s "$out/$name.stderr"; done
     cp ${view}/catalog.json "$out/catalog.json"
  ''
