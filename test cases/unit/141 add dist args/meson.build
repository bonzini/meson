project('add-dist-args', version: '1.0')

if import('fs').exists('distcheck.txt')
  assert(get_option('buildtype') == 'release')
endif

meson.add_dist_args('-Dbuildtype=release')
meson.add_dist_args('-Db_ndebug=true')
meson.add_dist_script('mark-dist.py')

testcase expect_error('meson.add_dist_args can only be used once if overwrite is true')
  meson.add_dist_args('-Dbuildtype=debug', overwrite: true)
endtestcase
