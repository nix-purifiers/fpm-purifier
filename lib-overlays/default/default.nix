# SPDX-License-Identifier: MIT
{ ... }:
{
  overlay = final: prev: {
    fpm-purifier = (prev.fpm-purifier or { }) // {
      readLock = import ./read-lock.nix { lib = final; };
    };
  };
}
