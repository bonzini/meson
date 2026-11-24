project('rustprog', 'c')

if not add_languages('rust', required : false)
  error('MESON_SKIP_TEST crt-static doesn\'t work')
endif

c_lib = static_library('lib', 'lib.c')
executable('main', 'main.rs', link_with : c_lib)

whole_lib = static_library('whole', 'whole.c')
e = executable('main_whole', 'main_whole.rs', link_whole : whole_lib)
test('link_whole', e)
