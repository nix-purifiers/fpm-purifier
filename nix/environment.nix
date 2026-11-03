{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  toolchain,
  nativeFpm,
  gfortran,
  gcc,
  sdkVersion,
}:
{
  lock,
  fetchers ? { },
  nativeBuildInputs ? [ ],
  buildFlags ? [ ],
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "locked-fortran-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  manifest = writeText "fpm-capture.json" (builtins.toJSON checked.data);
  selection =
    lib.concatMap
      (
        k:
        lib.optionals (checked.data.configuration.${k} != "") [
          "--${k}"
          checked.data.configuration.${k}
        ]
      )
      [
        "profile"
        "features"
      ];
in
assert checked.problems == [ ];
assert lib.assertMsg (
  checked.data.toolVersions == {
    sdk = sdkVersion;
    fpm = nativeFpm.version;
    gfortran = gfortran.version;
    gcc = gcc.version;
  }
) "Fortran SDK changed; update the lock";
runCommand "purified-fortran-environment"
  {
    nativeBuildInputs = [
      toolchain
      python3
    ]
    ++ nativeBuildInputs;
  }
  ''
    unset FPM_FC FPM_CC FPM_CXX FPM_AR FPM_FFLAGS FPM_CFLAGS FPM_CXXFLAGS FPM_LDFLAGS FC CC CXX AR FFLAGS CFLAGS CXXFLAGS LDFLAGS
    export OSTYPE=linux-gnu
    export FPM_FC=gfortran FPM_CC=gcc FPM_CXX=g++ FPM_AR=ar
    export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home" FPM_BUILD_DIR="$out/build" FPM_PURIFIER_FROZEN=1 FPM_PURIFIER_DEPS_ONLY=1
    mkdir -p "$HOME" "$out/build" project/src
    python3 -c 'import json,pathlib;d=json.load(open("${manifest}"));[(pathlib.Path("project",n).parent.mkdir(parents=True,exist_ok=True),pathlib.Path("project",n).write_text(v["content"])) for n,v in d["inputs"].items()]'
    python3 ${../fpm_purifier/stage.py} ${manifest} ${sources} "$out/build/cache.toml"
    cd project
    fpm build --no-prune --verbose ${lib.escapeShellArgs (selection ++ buildFlags)}
    fpm build --no-prune --show-model --dump "$TMPDIR/model.json" ${
      lib.escapeShellArgs (selection ++ buildFlags)
    } > "$TMPDIR/model-display.log"
    python3 ${../fpm_purifier/check-project.py} ${manifest} "$TMPDIR/model.json"
    cp ${manifest} "$out/capture.json"
    ln -s ${sources} "$out/sources"
  ''
