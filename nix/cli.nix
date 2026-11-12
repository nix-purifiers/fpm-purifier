{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  toolchain,
  nativeFpm,
  gfortran,
  gcc,
  cacert,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "fpm-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/fpm-purifier"
    cp -r fpm_purifier nix lib-overlays pkgs "$out/lib/fpm-purifier/"
    install -m755 bin/fpm-purifier "$out/bin/fpm-purifier"
    substituteInPlace "$out/lib/fpm-purifier/nix/realize.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/fpm-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set FPM_PURIFIER_NATIVE_FPM ${nativeFpm}/bin/fpm \
      --set FPM_PURIFIER_SDK_VERSION ${sdkVersion} --set FPM_PURIFIER_FPM_VERSION ${nativeFpm.version} \
      --set FPM_PURIFIER_GFORTRAN_VERSION ${gfortran.version} --set FPM_PURIFIER_GCC_VERSION ${gcc.version} \
      --set FPM_PURIFIER_SDK "$out" --set FPM_PURIFIER_TOOLCHAIN ${toolchain}
    makeWrapper "$out/bin/fpm-purifier" "$out/bin/fpm" --add-flags '--native --tool=fpm --'
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native Fortran fpm workflow with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "fpm-purifier";
  };
}
