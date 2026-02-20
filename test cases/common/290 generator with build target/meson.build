project('gen-buildtarget-test', 'c')

# A simple firmware binary we want to embed
fw = executable('firmware', 'firmware.c')

# A script that processes the binary (e.g. objcopy-style, bin to header)
gen = generator(
    find_program('bin2header.py'),
    output: '@PLAINNAME@.h',
    arguments: ['@INPUT@', '@OUTPUT@'],
)

# This should fail: passing a BuildTarget to generator.process
hdr = gen.process(fw)

exe = executable('main', 'main.c', hdr)
