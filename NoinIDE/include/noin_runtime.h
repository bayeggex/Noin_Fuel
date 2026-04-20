#ifndef NOIN_RUNTIME_H
#define NOIN_RUNTIME_H

#include <stdint.h>

void output(uint8_t pin);
void input(uint8_t pin);
void high(uint8_t pin);
void low(uint8_t pin);
void toggle(uint8_t pin);
uint8_t read(uint8_t pin);
void wait_ms(uint16_t ms);
void pwm_write(uint8_t pin, uint8_t value);
uint16_t analog_read(uint8_t pin);
int32_t map_value(int32_t x, int32_t in_min, int32_t in_max, int32_t out_min, int32_t out_max);
void serial_begin(uint32_t baud);
void print_int(int32_t value);
void print_str(const char *text);

#define noin_pin_output output
#define noin_pin_input input
#define noin_high high
#define noin_low low
#define noin_toggle toggle
#define noin_read read
#define noin_wait_ms wait_ms
#define noin_pwm_write pwm_write
#define noin_analog_read analog_read
#define noin_map map_value
#define noin_serial_begin serial_begin
#define noin_print_int print_int
#define noin_print_str print_str

#endif
