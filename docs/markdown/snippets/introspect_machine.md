## "machine" entry in target introspection data

The JSON data returned by `meson introspect --targets` now has a `machine`
entry in each `target_sources` block.  The new entry has value `unknown`
if the `language` is also unknown, or one of `build` and `host` otherwise.
