#[no_mangle]
pub static mut CTOR_RAN: i32 = 0;

pub fn main() {
    // The constructor in whole.c sets CTOR_RAN only if the whole library is linked.
    assert_eq!(unsafe { CTOR_RAN }, 1);
}
