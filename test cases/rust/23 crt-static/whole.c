/* Nothing references this object, so it is only linked with link_whole. */
extern int CTOR_RAN;

__attribute__((constructor)) static void set_ctor_ran(void)
{
    CTOR_RAN = 1;
}
