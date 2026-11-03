{
  symlinkJoin,
  nativeFpm,
  gfortran,
  gcc,
  git,
  nix-prefetch-git,
  curl,
  cacert,
  gnutar,
  gzip,
  coreutils,
  findutils,
}:
symlinkJoin {
  name = "fpm-purifier-toolchain";
  paths = [
    nativeFpm
    gfortran
    gcc
    git
    nix-prefetch-git
    curl
    cacert
    gnutar
    gzip
    coreutils
    findutils
  ];
}
