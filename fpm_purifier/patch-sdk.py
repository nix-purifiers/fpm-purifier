from pathlib import Path

p = Path("fpm.F90")
s = p.read_text()
old = "  use fpm_environment, only: get_os_type, OS_WINDOWS, os_is_unix"
assert s.count(old) == 1
s = s.replace(old, old + ", get_env")
old = """    if (allocated(dependency%git)) then
      call git_revision(proj_dir, revision, error)
      if (allocated(error)) return
    end if"""
assert s.count(old) == 1
s = s.replace(
    old,
    """    if (allocated(dependency%git)) then
      if (len(get_env("FPM_PURIFIER_FROZEN", "")) > 0) then
        if (.not.allocated(dependency%revision)) then
          call fatal_error(error, "Frozen fpm dependency has no locked revision")
          return
        end if
        revision = dependency%revision
      else
        call git_revision(proj_dir, revision, error)
        if (allocated(error)) return
      end if
    end if""",
)
old = """      if (fetch) then
        call dependency%git%checkout(proj_dir, error)"""
assert s.count(old) == 1
s = s.replace(
    old,
    """      if (fetch) then
        if (len(get_env("FPM_PURIFIER_FROZEN", "")) > 0) then
          call fatal_error(error, "Frozen fpm dependency is missing from prepared sources")
          return
        end if
        call dependency%git%checkout(proj_dir, error)""",
)
old = "use fpm_environment, only: get_os_type, OS_WINDOWS, OS_MACOS, library_filename"
assert s.count(old) == 1
s = s.replace(old, old + ", get_env")
old = """            call target%set_output_dir(get_output_dir(model%build_prefix, target%compile_flags))"""
assert s.count(old) == 1
s = s.replace(
    old,
    """            if (allocated(target%source) .and. target%package_name /= model%package_name &
                .and. len(get_env("FPM_PURIFIER_OBJECT_PREFIX", "")) > 0) then
              call target%set_output_dir(get_output_dir(get_env("FPM_PURIFIER_OBJECT_PREFIX", ""), target%compile_flags))
            else
              call target%set_output_dir(get_output_dir(model%build_prefix, target%compile_flags))
            end if""",
)
old = "    else\n      call dependency%get_from_registry(proj_dir, global_settings, error)"
assert s.count(old) == 1
s = s.replace(
    old,
    '    else\n      if (len(get_env("FPM_PURIFIER_FROZEN", "")) > 0) then\n        call fatal_error(error, "Frozen fpm dependency is missing from prepared sources")\n        return\n      end if\n      call dependency%get_from_registry(proj_dir, global_settings, error)',
)
start = s.index("subroutine build_model(model, settings, package_config, error)")
end = s.index("end subroutine build_model", start)
body = s[start:end]
a = "    ! Add sources from executable directories"
b = "    if (settings%verbose) then\n        write(*,*)'<INFO> BUILD_NAME:"
assert body.count(a) == 1 and body.count(b) == 1
body = body.replace(
    a, '    if (len(get_env("FPM_PURIFIER_DEPS_ONLY", "")) == 0) then\n' + a
)
body = body.replace(b, "    endif\n\n" + b)
a = "if (is_dir(lib_dir)) then"
assert body.count(a) == 1
body = body.replace(
    a,
    'if (is_dir(lib_dir) .and. (i /= 1 .or. len(get_env("FPM_PURIFIER_DEPS_ONLY", "")) == 0)) then',
)
s = s[:start] + body + s[end:]
p.write_text(s)
