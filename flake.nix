{
  description = "Locked, Nix-resolved Fortran fpm dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        fpm-purifier = final.lib.makeScope final.newScope (scope: {
          nativeFpm = scope.callPackage ./nix/native.nix { };
          toolchain = scope.callPackage ./nix/toolchain.nix { };
          sdkVersion = import ./nix/sdk-version.nix { nixpkgsSrc = nixpkgs; };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildFortranProject = scope.callPackage ./pkgs/build-fortran-project {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).fpm-purifier.cli;
        cli = self.packages.${system}.default;
        sdk = (pkgsFor system).fpm-purifier.toolchain;
      });
      lib.fpm-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default { }).overlay).fpm-purifier;
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/fpm-purifier";
          meta.description = "Lock native Fortran dependencies";
        };
      });
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.fpm-purifier.buildFortranProject { src = ./examples/minimal; };
          consumer = pkgs.writeText "consumer.f90" ''
            program consumer
            use purifier_proof, only: answer
            implicit none
            if(answer()/=42)error stop 1
            print *,answer()
            end program consumer
          '';
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
          installed =
            pkgs.runCommand "fortran-installed-consumer"
              {
                nativeBuildInputs = [
                  pkgs.gfortran
                  pkgs.python3
                ];
              }
              ''
                python3 -c 'import pathlib,subprocess;roots=[pathlib.Path("${build.packages.project}/build"),pathlib.Path("${build.packages.environment}/build")];mods=sorted({str(p.parent) for r in roots for p in r.rglob("*.mod")});libs=list(roots[0].rglob("libpurifier-proof.a"));assert len(libs)==1;subprocess.run(["gfortran",*[flag for p in mods for flag in ["-I",p]],"${consumer}",str(libs[0]),"-o","consumer"],check=True)'
                ./consumer > answer
                mkdir "$out"
                cp answer "$out/answer"
              '';
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
