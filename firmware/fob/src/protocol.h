/* The iphone-remote over-the-air protocol, version 1 (docs/protocol.md, IREM-2).
 * Pure functions, no Zephyr: unit tested on the host (tests/). */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define FOB_PROTOCOL_VERSION 0x01
#define FOB_COMPANY_ID 0xFFFF
#define FOB_MAX_ID 7

/* Manufacturer data: company ID (2, little-endian) + version, fob_id, counter (2), battery. */
#define FOB_MFG_LEN 7

/* The press UUID 3B89DBAA-2669-4548-9D04-6876798D0903, on-air order (least significant first). */
extern const uint8_t fob_press_uuid[16];

/* Battery byte: VDD in 20 mV units, 0 = not measured, clamped to 1..255. */
uint8_t fob_battery_byte(int vdd_mv);

/* Fills out[FOB_MFG_LEN] with the manufacturer data of a press. */
void fob_press_mfg(uint8_t out[FOB_MFG_LEN], uint8_t fob_id, uint16_t counter, uint8_t battery);

/* Whether a 128-bit UUID as received on air (16 bytes, least significant first) is the ack
 * for (fob_id, counter). */
bool fob_is_ack(const uint8_t *uuid, size_t len, uint8_t fob_id, uint16_t counter);

/* Whether any 128-bit UUID in a list AD's data (len a multiple of 16) is that ack. */
bool fob_list_has_ack(const uint8_t *data, size_t len, uint8_t fob_id, uint16_t counter);

/* The fob ID from the three jumper pins as read (1 = high = open); closed (low) is a 1 bit. */
uint8_t fob_id_from_pins(int bit0, int bit1, int bit2);
