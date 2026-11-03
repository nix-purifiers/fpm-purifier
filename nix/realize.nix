{
  project,
  companion,
  target ? "environment",
  sdk ? null,
  profile ? false,
  flags ? "[]",
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativeFpm = pkgs.callPackage ./native.nix { };
  toolchain = pkgs.callPackage ./toolchain.nix { inherit nativeFpm; };
  sdkVersion = import ./sdk-version.nix { inherit nixpkgsSrc; };
  args = {
    src = /. + project;
    lockFile = /. + companion;
  };
  lock = import ./read-lock.nix { inherit (pkgs) lib; } args;
  output =
    if target == "environment" then
      pkgs.callPackage ./environment.nix
        {
          inherit
            purifier
            nativeFpm
            toolchain
            sdkVersion
            ;
        }
        {
          inherit lock;
          buildFlags = builtins.fromJSON flags;
        }
    else if target == "release" then
      (pkgs.callPackage ./build-project.nix {
        inherit
          purifier
          nativeFpm
          toolchain
          sdkVersion
          ;
      } args).release
    else
      throw "fpm-purifier: unknown target";
in
if profile then
  pkgs.writeText "fpm-${target}-profile.json" (
    builtins.toJSON {
      inherit output;
      sdk = builtins.storePath sdk;
    }
  )
else
  output
