MCU ?= atmega328p
F_CPU ?= 16000000UL
PROGRAMMER = arduino
PORT = COM3
BAUD = 115200
AVRDUDE_CONF =
AVRDUDE_PART ?= m328p
AVRDUDE_FLAGS ?= -v -D
AVRDUDE_MEMORY ?= flash
AVRDUDE_OPERATION ?= w
AVRDUDE_FORMAT ?= i

TARGET = app
SRC = main.c src/noin_runtime.c src/program.generated.c

CC ?= avr-gcc
OBJCOPY ?= avr-objcopy
SIZE ?= avr-size
AVRDUDE ?= avrdude

AVRDUDE_CONF_ARG = $(if $(AVRDUDE_CONF),-C "$(AVRDUDE_CONF)",)

CFLAGS = -std=c11 -Wall -Wextra -Os -mmcu=$(MCU) -DF_CPU=$(F_CPU) -Iinclude

all: $(TARGET).hex size

$(TARGET).elf: $(SRC)
	$(CC) $(CFLAGS) -o $@ $^

$(TARGET).hex: $(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@

size: $(TARGET).elf
	$(SIZE) -C --mcu=$(MCU) $<

flash: $(TARGET).hex
	$(AVRDUDE) $(AVRDUDE_CONF_ARG) -p $(AVRDUDE_PART) -c $(PROGRAMMER) -P $(PORT) -b $(BAUD) $(AVRDUDE_FLAGS) -U $(AVRDUDE_MEMORY):$(AVRDUDE_OPERATION):$<:$(AVRDUDE_FORMAT)

clean:
	del /Q $(TARGET).elf $(TARGET).hex 2>NUL || exit 0

.PHONY: all flash clean size
