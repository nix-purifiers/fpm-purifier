{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  writeShellScript,
  purifier,
  nativeFpm,
  toolchain,
  gfortran,
  gcc,
  sdkVersion,
}:
{
  src,
  lockFile ? src + "/fpm-purifier.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  buildFlags ? [ ],
  doCheck ? true,
  buildCommand ? "fpm build",
  checkCommand ? "fpm test",
  installCommand ? "",
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".fpm-purifier"
      "build"
      "result"
      "__pycache__"
    ]),
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  environment =
    import ./environment.nix
      {
        inherit
          lib
          runCommand
          fetchgit
          python3
          writeText
          purifier
          nativeFpm
          toolchain
          gfortran
          gcc
          sdkVersion
          ;
      }
      {
        inherit
          lock
          fetchers
          nativeBuildInputs
          buildFlags
          ;
      };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  manifest = writeText "fpm-project-capture.json" (builtins.toJSON lock.data);
  selection =
    lib.concatMap
      (
        k:
        lib.optionals (lock.data.configuration.${k} != "") [
          "--${k}"
          lock.data.configuration.${k}
        ]
      )
      [
        "profile"
        "features"
      ];
  configured = writeShellScript "configured-fpm" ''
    if [ "$#" -eq 0 ]; then exec ${nativeFpm}/bin/fpm; fi
    purifier_command="$1"
    shift
    case "$purifier_command" in
      build|test|run|install) exec ${nativeFpm}/bin/fpm "$purifier_command" ${
        lib.escapeShellArgs (selection ++ buildFlags)
      } "$@" ;;
      *) exec ${nativeFpm}/bin/fpm "$purifier_command" "$@" ;;
    esac
  '';
  project =
    runCommand "purified-fortran-project"
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
        export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home" FPM_BUILD_DIR="$out/build" FPM_PURIFIER_FROZEN=1
        export FPM_PURIFIER_OBJECT_PREFIX=${environment}/build/gfortran
        mkdir -p "$HOME" "$out/build" "$out/source" "$out/bin" runner
        cp -pr ${source}/. "$out/source/"
        chmod -R u+w "$out/source"
        cp ${environment}/build/cache.toml "$out/build/cache.toml"
        chmod u+w "$out/build/cache.toml"
        ln -s ${configured} "$PWD/runner/fpm"
        export PATH="$PWD/runner:$PATH"
        cd "$out/source"
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ${installCommand}
        fpm build --show-model --dump "$out/model.json" > "$TMPDIR/model-display.log"
        python3 ${../fpm_purifier/check-project.py} ${manifest} "$out/model.json"
      '';
  release =
    runCommand "fpm-source-release"
      {
        nativeBuildInputs = [
          toolchain
          python3
        ];
      }
      ''
        export HOME="$TMPDIR/home"
        mkdir -p "$HOME" "$out" source
        cp -pr ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/fpm-purifier.lock.json
        python3 ${../fpm_purifier/release.py} ${manifest} "$PWD/source" "$out" ${nativeFpm}/bin/fpm
      '';
in
assert lock.problems == [ ];
assert lib.assertMsg (
  lock.data.toolVersions == {
    sdk = sdkVersion;
    fpm = nativeFpm.version;
    gfortran = gfortran.version;
    gcc = gcc.version;
  }
) "Fortran SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project environment;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
