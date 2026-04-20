#include "noin_runtime.h"
#include "noin_program.h"

static void setup(void);
static void run(void);

static void setup(void)
{
    noin_pin_output(13);
    noin_serial_begin(115200);
    noin_print_str("Noin is ready");
}
static void run(void)
{
    noin_toggle(13);
    noin_wait_ms(500);
}

void noin_run(void)
{
    setup();
    while (1)
    {
        run();
    }
}
