# fpm-purifier

Locked, Nix-resolved dependencies for the Fortran Package Manager.

## Quickstart

Start in a native fpm project with an explicit version in `fpm.toml`.

```sh
nix shell 'github:nix-purifiers/fpm-purifier'
fpm-purifier lock
fpm build
fpm test
```

The shell supplies an `fpm` wrapper and pinned GNU compilers. Dependencies are
compiled in Nix. Native fpm then reuses their readonly objects and module files
while building your own source in a private `.fpm-purifier/` directory. Its
native source scanner, compiler commands, dependency ordering and linker remain
in use. An existing `build/` directory remains separate.

Without a companion lockfile, the wrapper warns and runs ordinary, impure fpm.
A stale or invalid lock fails. Commit `fpm-purifier.lock.json`; refresh it after
changing dependency metadata:

```sh
fpm-purifier lock --update
```

Source edits do not require relocking. Use `lock --input path` to track other
files that affect selection. `prefetch` prepares the compiled dependencies.
Wrappers can also be installed using your normal Nix configuration.

## Configuration

A lock selects a native configuration. To select a profile or feature set:

```sh
fpm-purifier lock --update --profile release
fpm test
```

Alternatively, use `--features feature1,feature2` when locking. Native commands
inherit that selection; an explicit conflicting selection requires relocking.
Additional `--flag`, `--c-flag`, `--cxx-flag` and `--link-flag` values select a
matching pure dependency build. The compiler remains pinned to the GNU SDK.

## What is locked

The native fpm build model selects and exports the transitive dependency graph.
Each Git dependency is pinned to its resolved commit and Nix tree hash. The
captured native checkout must match that fetched tree. The companion also records
metadata inputs, selected configuration, package versions and SDK identity.

The prepared environment verifies native dependency versions, revisions and
edges against the lock. Native commands use that cache and the compiled objects;
missing dependencies fail before fetching. Native model dumps retain the Nix
source locations used by compiler and editor tooling.

This integration currently supports fpm 0.13, GNU Fortran and Git dependencies.
Registry dependencies, local-path dependency workspaces and metapackages that
fetch additional tools are outside its current scope. Use a literal version
string in `fpm.toml`. SDK changes require relocking.

## Commands

```sh
fpm-purifier exec -- fpm test
fpm-purifier release
fpm-purifier publish \
  --repo owner/project --tag v0.1.0
```

`release` produces a reproducible source tarball containing the companion.
Ordinary fpm users can unpack it and build or test it. `publish` creates or
updates a GitHub release with those same bytes. This source bundle is separate
from the native fpm registry, whose publication rules reject Git dependencies.

Use `--project` and `--lock-file` to select an external companion. Native commands
also accept `FPM_PURIFIER_PROJECT` and `FPM_PURIFIER_LOCK`. Environment profiles
retain dependencies and the wrapper SDK as Nix garbage collector roots.

## Building with Nix

An optional project Nix definition can call the overlay's
`fpm-purifier.buildFortranProject` through `callPackage`:

```nix
pkgs.fpm-purifier.buildFortranProject {
  src = ./.;
  buildCommand = "fpm build";
  checkCommand = "fpm test";
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`packages.environment` contains compiled dependency objects and module files;
`packages.project` contains the compiled project and its native model under
`build/` and `model.json`. Override `installCommand` for the project's installation
layout, or `nativeBuildInputs` and `buildFlags` for its build requirements.

## Native C ABI projections

An opt-in `nativeProducts` declaration selects the locked root library after
native fpm builds and installs it. Configure fpm to build a shared library and
write the public Fortran procedures with `bind(C)`, then declare their C symbols:

```nix
pkgs.fpm-purifier.buildFortranProject {
  src = ./.;
  nativeProducts.my-library = {
    abi = "c";
    exports = [ "my_library_answer" ];
    runtime = {
      kind = "gfortran";
      lifecycle = "caller-managed";
    };
  };
}
```

The key must match the locked root package name. `exports` contains distinct,
explicit C names actually defined by the native root library. Consumers supply
compatible signatures, manage any initialization and finalization required by
their API, and finish calls and release retained native state before closing a
library. The tested `bind(C)` fixture returns values and retains no allocated
state across calls; this does not establish universal initialization or safe
unloading for arbitrary Fortran code.

When selected, the default install hook runs native
`fpm install --prefix "$out" --no-rebuild`. Both the result and
`packages.project` expose `projections.native`, `projections.python-ffi` and
`projections.java-ffi`. Their `catalog.json` records exact installed library
paths, declared exports/lifecycle, compiler/runtime identities and the native
model path. `purifier_native.py` loads libraries lazily with ctypes; `java.args`
provides the library search path. These views retain the producer's installed
dependency libraries and runtime closure. Loading does not generate bindings or
run API initialization routines.

A unique native-built root artifact must be an ELF shared library for the target
architecture. Static archives, PIE executables, missing C exports, ambiguous
artifacts, escaping paths and altered installed bytes are rejected. A custom
`installCommand` must preserve the checked native root and dependency artifacts
inside the output. Loader checks reject unresolved dependencies and require the
recorded Fortran runtime, without ambient library-path overrides. Resolved native
dependencies must match the selected installed files, even when another Nix-store
library has the same dependency name.
The native fpm model and actual output drive this check; the purifier does not
reinterpret fpm feature/profile selection or infer a C ABI from a `.so` suffix.
Native Fortran `.mod` files are compiler-specific and are not advertised as C
headers. Defaults and existing locks keep their ordinary build behavior with
empty projections.

The host test captures the actual runner graph with `jonquil` and `toml-f`,
then exercises C, ctypes, CFFI and scoped Java FFM calls. Function-pointer checks
verify the root, installed dependencies and pinned GNU Fortran runtime origins.
The static baseline and a shared build without the declared `bind(C)` export
remain explicit controls. Runtime support on each Linux architecture requires
its native CI run.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
