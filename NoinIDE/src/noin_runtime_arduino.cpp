#ifdef ARDUINO
#include <Arduino.h>
#else
#include <stdint.h>

#define INPUT 0
#define OUTPUT 1
#define HIGH 1
#define LOW 0

inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t, uint8_t) {}
inline int digitalRead(uint8_t) { return 0; }
inline void delay(uint32_t) {}
inline int analogRead(uint8_t) { return 0; }
inline void analogWrite(uint8_t, int) {}

struct SerialMock {
    void begin(uint32_t) {}
    void println(int32_t) {}
    void println(const char *) {}
};

static SerialMock Serial;
#endif

#include "noin_runtime.h"

void output(uint8_t pin)
{
    pinMode(pin, OUTPUT);
}

void input(uint8_t pin)
{
    pinMode(pin, INPUT);
}

void high(uint8_t pin)
{
    digitalWrite(pin, HIGH);
}

void low(uint8_t pin)
{
    digitalWrite(pin, LOW);
}

void toggle(uint8_t pin)
{
    digitalWrite(pin, (digitalRead(pin) == HIGH) ? LOW : HIGH);
}

uint8_t read(uint8_t pin)
{
    return (digitalRead(pin) == HIGH) ? 1 : 0;
}

void wait_ms(uint16_t ms)
{
    delay(ms);
}

void pwm_write(uint8_t pin, uint8_t value)
{
    analogWrite(pin, value);
}

uint16_t analog_read(uint8_t pin)
{
    return static_cast<uint16_t>(analogRead(pin));
}

int32_t map_value(int32_t x, int32_t in_min, int32_t in_max, int32_t out_min, int32_t out_max)
{
    if (in_max == in_min)
    {
        return out_min;
    }
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

void serial_begin(uint32_t baud)
{
    Serial.begin(baud);
}

void print_int(int32_t value)
{
    Serial.println(value);
}

void print_str(const char *text)
{
    Serial.println(text);
}
