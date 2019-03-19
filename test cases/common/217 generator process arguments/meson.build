project('generator process arguments', 'c')

cp = find_program('cp.py')

a = configure_file(input: 'a.c', output: 'out_a.c', copy: true)
f = custom_target('customtarget1', input: 'f.c', output: 'out_f.c',
                  command: [cp, '@INPUT@', '@OUTPUT@'])
subdir('subdir')

cp = generator(cp, output: '@PLAINNAME@',
               arguments: ['@INPUT@', '@OUTPUT@'])
executable('prog1', sources: [
    cp.process(a, f, g[0])
])
executable('prog2', sources: [
    cp.process(a, f, g[0], preserve_path_from: meson.build_root())
])

