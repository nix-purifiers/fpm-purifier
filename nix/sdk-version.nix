{ nixpkgsSrc }:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    patch = builtins.hashFile "sha256" ../fpm_purifier/patch-sdk.py;
    native = builtins.hashFile "sha256" ./native.nix;
  }
)
