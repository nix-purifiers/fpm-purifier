{ lib }:
{
  src,
  lockFile ? src + "/fpm-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  inputs = data.inputs or { };
  safe =
    s: builtins.isString s && s != "." && s != ".." && builtins.match "[A-Za-z0-9_.-]+" s != null;
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  sha1 = s: builtins.isString s && builtins.match "[0-9a-f]{40}" s != null;
  manifest = if inputs ? "fpm.toml" then builtins.fromTOML inputs."fpm.toml".content else { };
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "fpm"
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs inputs
    &&
      builtins.attrNames inputs
      == builtins.sort builtins.lessThan (lib.unique ([ "fpm.toml" ] ++ data.extraInputs))
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs inputs.${name}
      && builtins.isString (inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && (builtins.readDir (dirOf (src + "/${name}"))).${baseNameOf name} == "regular"
      && builtins.hashFile "sha256" (src + "/${name}") == (inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" inputs.${name}.content == inputs.${name}.sha256
    ) (builtins.attrNames inputs)
    && builtins.isAttrs (data.project or null)
    && safe (data.project.name or null)
    && builtins.isString (data.project.version or null)
    && data.project.name == (manifest.name or null)
    && data.project.version == (manifest.version or null)
    && builtins.isAttrs (data.configuration or null)
    &&
      builtins.attrNames data.configuration == [
        "features"
        "profile"
      ]
    && builtins.all (k: builtins.isString data.configuration.${k}) [
      "features"
      "profile"
    ]
    && !(data.configuration.features != "" && data.configuration.profile != "")
    && builtins.isList entries
    && builtins.isList nodes
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && lib.hasPrefix "git/" e.path
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isAttrs (e.git or null)
      && builtins.isString (e.git.url or null)
      && sha1 (e.git.rev or null)
      && (e.git.submodules or null) == false
      && (e.git.leaveDotGit or null) == false
      && e.git ? commitObject
      && e.git.commitObject == null
      && !(e ? url)
    ) entries
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && builtins.isString (n.version or null)
      && (n.entry or null) == "git/${n.name}"
      && builtins.isString (n.url or null)
      && sha1 (n.revision or null)
      && n ? requested
      && (n.requested == null || builtins.isString n.requested)
      && builtins.isList (n.dependencies or null)
      && builtins.all (d: builtins.any (other: other.name == d) nodes) n.dependencies
      && builtins.any (e: e.path == n.entry && e.git.url == n.url && e.git.rev == n.revision) entries
    ) nodes
    && builtins.length nodes == builtins.length entries
    && builtins.length (lib.unique (map (n: n.name) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.isAttrs (data.toolVersions or null)
    && builtins.all (k: builtins.isString (data.toolVersions.${k} or null)) [
      "sdk"
      "fpm"
      "gfortran"
      "gcc"
    ];
in
{
  purifier = "fpm";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Fortran lock is missing, stale, or unsupported; run fpm-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
