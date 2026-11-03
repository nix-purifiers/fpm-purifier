{
  stdenv,
  fortran-fpm,
  gfortran,
  python3,
}:
stdenv.mkDerivation {
  pname = "fpm-purifier-sdk";
  version = fortran-fpm.version;
  src = fortran-fpm.src;
  dontUnpack = true;
  nativeBuildInputs = [
    gfortran
    python3
  ];
  buildPhase = ''
    cp "$src" fpm.F90
    chmod u+w fpm.F90
    python ${../fpm_purifier/patch-sdk.py}
    mkdir modules
    gfortran -J modules -ffree-line-length-none -o fpm fpm.F90
  '';
  installPhase = ''
    mkdir -p "$out/bin"
    cp fpm "$out/bin/fpm"
  '';
}
