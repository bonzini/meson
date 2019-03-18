project('generator file arguments', 'c')

cp = find_program('cp.py')

a = configure_file(input: 'a.c', output: 'out_a.c', copy: true)
f = custom_target('customtarget1', input: 'f.c', output: 'out_f.c',
                  command: [cp, '@INPUT@', '@OUTPUT@'])
subdir('subdir')

executable('prog', sources: [
    # This is not a very "normal" or even sensible use of generator's
    # "arguments" kwarg; it's just to test passing various kinds of
    # objects as arguments.
    #
    # The use case for this feature is to pass a file every time a
    # generator is invoked, without having to specify it repeatedly
    # in "process".
    generator(cp, output: '@PLAINNAME@_a.c',
          arguments: [a, '@OUTPUT@']).process(files('gen')),
    generator(cp, output: '@PLAINNAME@_f.c',
          arguments: [f, '@OUTPUT@']).process(files('gen')),
    generator(cp, output: '@PLAINNAME@_g.c',
          arguments: [g[0], '@OUTPUT@']).process(files('gen')),
    generator(cp, output: '@PLAINNAME@_h.c',
          arguments: [files('h.c'), '@OUTPUT@']).process(files('gen'))
])

