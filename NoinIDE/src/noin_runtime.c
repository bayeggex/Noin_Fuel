#define F_CPU 16000000UL

#include <avr/io.h>
#include <util/delay.h>

#include "noin_runtime.h"

static uint8_t g_serial_ready = 0;

static uint32_t abs_diff_u32(uint32_t a, uint32_t b)
{
    return (a > b) ? (a - b) : (b - a);
}

static void serial_write_byte(uint8_t value)
{
    if (!g_serial_ready)
    {
        return;
    }

    while (!(UCSR0A & (1 << UDRE0)))
    {
    }
    UDR0 = value;
}

static void serial_write_text(const char *text)
{
    while (*text)
    {
        serial_write_byte((uint8_t)*text++);
    }
}

static void pin_to_ddr_bit(uint8_t pin, volatile uint8_t **ddr, uint8_t *bit)
{
    switch (pin)
    {
        case 0: *ddr = &DDRD; *bit = PD0; return;
        case 1: *ddr = &DDRD; *bit = PD1; return;
        case 2: *ddr = &DDRD; *bit = PD2; return;
        case 3: *ddr = &DDRD; *bit = PD3; return;
        case 4: *ddr = &DDRD; *bit = PD4; return;
        case 5: *ddr = &DDRD; *bit = PD5; return;
        case 6: *ddr = &DDRD; *bit = PD6; return;
        case 7: *ddr = &DDRD; *bit = PD7; return;
        case 8: *ddr = &DDRB; *bit = PB0; return;
        case 9: *ddr = &DDRB; *bit = PB1; return;
        case 10: *ddr = &DDRB; *bit = PB2; return;
        case 11: *ddr = &DDRB; *bit = PB3; return;
        case 12: *ddr = &DDRB; *bit = PB4; return;
        case 13: *ddr = &DDRB; *bit = PB5; return;
        default: *ddr = 0; *bit = 0; return;
    }
}

static void pin_to_port_bit(uint8_t pin, volatile uint8_t **port, uint8_t *bit)
{
    switch (pin)
    {
        case 0: *port = &PORTD; *bit = PD0; return;
        case 1: *port = &PORTD; *bit = PD1; return;
        case 2: *port = &PORTD; *bit = PD2; return;
        case 3: *port = &PORTD; *bit = PD3; return;
        case 4: *port = &PORTD; *bit = PD4; return;
        case 5: *port = &PORTD; *bit = PD5; return;
        case 6: *port = &PORTD; *bit = PD6; return;
        case 7: *port = &PORTD; *bit = PD7; return;
        case 8: *port = &PORTB; *bit = PB0; return;
        case 9: *port = &PORTB; *bit = PB1; return;
        case 10: *port = &PORTB; *bit = PB2; return;
        case 11: *port = &PORTB; *bit = PB3; return;
        case 12: *port = &PORTB; *bit = PB4; return;
        case 13: *port = &PORTB; *bit = PB5; return;
        default: *port = 0; *bit = 0; return;
    }
}

static void pin_to_pinreg_bit(uint8_t pin, volatile uint8_t **pinreg, uint8_t *bit)
{
    switch (pin)
    {
        case 0: *pinreg = &PIND; *bit = PD0; return;
        case 1: *pinreg = &PIND; *bit = PD1; return;
        case 2: *pinreg = &PIND; *bit = PD2; return;
        case 3: *pinreg = &PIND; *bit = PD3; return;
        case 4: *pinreg = &PIND; *bit = PD4; return;
        case 5: *pinreg = &PIND; *bit = PD5; return;
        case 6: *pinreg = &PIND; *bit = PD6; return;
        case 7: *pinreg = &PIND; *bit = PD7; return;
        case 8: *pinreg = &PINB; *bit = PB0; return;
        case 9: *pinreg = &PINB; *bit = PB1; return;
        case 10: *pinreg = &PINB; *bit = PB2; return;
        case 11: *pinreg = &PINB; *bit = PB3; return;
        case 12: *pinreg = &PINB; *bit = PB4; return;
        case 13: *pinreg = &PINB; *bit = PB5; return;
        default: *pinreg = 0; *bit = 0; return;
    }
}

void output(uint8_t pin)
{
    volatile uint8_t *ddr;
    uint8_t bit;

    pin_to_ddr_bit(pin, &ddr, &bit);
    if (ddr)
    {
        *ddr |= (1 << bit);
    }
}

void input(uint8_t pin)
{
    volatile uint8_t *ddr;
    uint8_t bit;

    pin_to_ddr_bit(pin, &ddr, &bit);
    if (ddr)
    {
        *ddr &= ~(1 << bit);
    }
}

void high(uint8_t pin)
{
    volatile uint8_t *port;
    uint8_t bit;

    pin_to_port_bit(pin, &port, &bit);
    if (port)
    {
        *port |= (1 << bit);
    }
}

void low(uint8_t pin)
{
    volatile uint8_t *port;
    uint8_t bit;

    pin_to_port_bit(pin, &port, &bit);
    if (port)
    {
        *port &= ~(1 << bit);
    }
}

void toggle(uint8_t pin)
{
    volatile uint8_t *port;
    uint8_t bit;

    pin_to_port_bit(pin, &port, &bit);
    if (port)
    {
        *port ^= (1 << bit);
    }
}

uint8_t read(uint8_t pin)
{
    volatile uint8_t *pinreg;
    uint8_t bit;

    pin_to_pinreg_bit(pin, &pinreg, &bit);
    if (!pinreg)
    {
        return 0;
    }

    return ((*pinreg & (1 << bit)) != 0) ? 1 : 0;
}

void wait_ms(uint16_t ms)
{
    while (ms--)
    {
        _delay_ms(1);
    }
}

int32_t map_value(int32_t x, int32_t in_min, int32_t in_max, int32_t out_min, int32_t out_max)
{
    int32_t in_span;
    int32_t out_span;

    if (in_max == in_min)
    {
        return out_min;
    }

    in_span = in_max - in_min;
    out_span = out_max - out_min;
    return (x - in_min) * out_span / in_span + out_min;
}

uint16_t analog_read(uint8_t pin)
{
    uint8_t channel;

    if (pin >= 14U && pin <= 19U)
    {
        channel = (uint8_t)(pin - 14U);
    }
    else if (pin <= 5U)
    {
        channel = pin;
    }
    else
    {
        return 0;
    }

    ADMUX = (1 << REFS0) | (channel & 0x0F);
    ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0);
    ADCSRA |= (1 << ADSC);

    while (ADCSRA & (1 << ADSC))
    {
    }

    return ADC;
}

void pwm_write(uint8_t pin, uint8_t value)
{
    switch (pin)
    {
        case 3:
            output(3);
            TCCR2A |= (1 << WGM21) | (1 << WGM20) | (1 << COM2B1);
            TCCR2B = (TCCR2B & ~((1 << CS22) | (1 << CS21) | (1 << CS20))) | (1 << CS22);
            OCR2B = value;
            return;
        case 5:
            output(5);
            TCCR0A |= (1 << WGM01) | (1 << WGM00) | (1 << COM0B1);
            TCCR0B = (TCCR0B & ~((1 << CS02) | (1 << CS01) | (1 << CS00))) | (1 << CS01) | (1 << CS00);
            OCR0B = value;
            return;
        case 6:
            output(6);
            TCCR0A |= (1 << WGM01) | (1 << WGM00) | (1 << COM0A1);
            TCCR0B = (TCCR0B & ~((1 << CS02) | (1 << CS01) | (1 << CS00))) | (1 << CS01) | (1 << CS00);
            OCR0A = value;
            return;
        case 9:
            output(9);
            TCCR1A |= (1 << WGM10) | (1 << COM1A1);
            TCCR1B = (TCCR1B & ~((1 << WGM13) | (1 << WGM12) | (1 << CS12) | (1 << CS11) | (1 << CS10))) | (1 << WGM12) | (1 << CS11) | (1 << CS10);
            OCR1A = value;
            return;
        case 10:
            output(10);
            TCCR1A |= (1 << WGM10) | (1 << COM1B1);
            TCCR1B = (TCCR1B & ~((1 << WGM13) | (1 << WGM12) | (1 << CS12) | (1 << CS11) | (1 << CS10))) | (1 << WGM12) | (1 << CS11) | (1 << CS10);
            OCR1B = value;
            return;
        case 11:
            output(11);
            TCCR2A |= (1 << WGM21) | (1 << WGM20) | (1 << COM2A1);
            TCCR2B = (TCCR2B & ~((1 << CS22) | (1 << CS21) | (1 << CS20))) | (1 << CS22);
            OCR2A = value;
            return;
        default:
            output(pin);
            if (value >= 128U)
            {
                high(pin);
            }
            else
            {
                low(pin);
            }
            return;
    }
}

void serial_begin(uint32_t baud)
{
    uint32_t ubrr_normal;
    uint32_t ubrr_u2x;
    uint32_t actual_normal;
    uint32_t actual_u2x;
    uint32_t err_normal;
    uint32_t err_u2x;
    uint32_t selected_ubrr;
    uint8_t use_u2x;

    if (baud == 0)
    {
        return;
    }

    ubrr_normal = (F_CPU / (16UL * baud));
    ubrr_u2x = (F_CPU / (8UL * baud));

    if (ubrr_normal > 0)
    {
        ubrr_normal -= 1UL;
    }
    if (ubrr_u2x > 0)
    {
        ubrr_u2x -= 1UL;
    }

    if (ubrr_normal > 4095UL)
    {
        ubrr_normal = 4095UL;
    }
    if (ubrr_u2x > 4095UL)
    {
        ubrr_u2x = 4095UL;
    }

    actual_normal = F_CPU / (16UL * (ubrr_normal + 1UL));
    actual_u2x = F_CPU / (8UL * (ubrr_u2x + 1UL));
    err_normal = abs_diff_u32(actual_normal, baud);
    err_u2x = abs_diff_u32(actual_u2x, baud);

    use_u2x = (err_u2x <= err_normal) ? 1U : 0U;
    selected_ubrr = use_u2x ? ubrr_u2x : ubrr_normal;

    UBRR0H = (uint8_t)(selected_ubrr >> 8);
    UBRR0L = (uint8_t)(selected_ubrr & 0xFF);

    UCSR0A = use_u2x ? (1 << U2X0) : 0;
    UCSR0B = (1 << TXEN0);
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);

    g_serial_ready = 1;
}

void print_int(int32_t value)
{
    char buffer[16];
    uint8_t i = 0;
    uint32_t x;

    if (!g_serial_ready)
    {
        serial_begin(115200);
    }

    if (value < 0)
    {
        serial_write_byte('-');
        x = (uint32_t)(-value);
    }
    else
    {
        x = (uint32_t)value;
    }

    do
    {
        buffer[i++] = (char)('0' + (x % 10U));
        x /= 10U;
    } while (x != 0U);

    while (i > 0)
    {
        serial_write_byte((uint8_t)buffer[--i]);
    }

    serial_write_text("\r\n");
}

void print_str(const char *text)
{
    if (!g_serial_ready)
    {
        serial_begin(115200);
    }

    if (!text)
    {
        return;
    }

    serial_write_text(text);
    serial_write_text("\r\n");
}
