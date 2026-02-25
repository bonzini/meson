## Shared module naming with `namingscheme=platform`

When using the `namingscheme=platform` option, `shared_module()` targets
on macOS now use the `.so` extension instead of `.dylib`. This reflects
the fact that shared modules are Mach-O bundles (built with `-bundle`)
intended for `dlopen()`, not shared libraries meant for `-l` linking.
Many real-world plugin systems (Python extensions, Apache modules,
PostgreSQL extensions) already use `.so` on macOS.

On iOS, where shared modules use `-dynamiclib` instead of `-bundle`,
the `.dylib` extension is preserved.

The `name_suffix` kwarg can still be used to override the default.
