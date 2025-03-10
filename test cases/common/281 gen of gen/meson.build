project('gentest', 'c')

if meson.backend() == 'xcode'
    error('MESON_SKIP_TEST: nested generators not supported in Xcode. Patches welcome.')
endif

cat = find_program('cat.py')
copy = find_program('cp.py')

gen1 = generator(copy, arguments: ['@INPUT@', '@OUTPUT@'], output: '@BASENAME@.g1')
gen2 = generator(copy, arguments: ['@INPUT@', '@OUTPUT@'], output: '@BASENAME@.g2')

res1 = gen1.process('blank.txt')
res2 = gen2.process(res1)
custom_target(
    output: 'b.out',
    input: [res1, res2],
    command: [cat, '@INPUT@'],
    capture: true,
    build_by_default: true,
)
