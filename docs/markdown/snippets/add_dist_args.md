## It is now possible to customize the setup arguments to meson dist

A new function has been added: [[meson.add_dist_args]]. This allows specifying
arguments which will be used by `meson dist` and the generated `ninja dist`
target to customize how the distcheck stage will configure the build. By default
a distcheck simply uses the same configuration as the main build.
