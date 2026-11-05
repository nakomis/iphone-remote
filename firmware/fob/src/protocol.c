#include "protocol.h"

#include <string.h>

/* 3B89DBAA-2669-4548-9D04-6876798D0903, reversed. */
const uint8_t fob_press_uuid[16] = {
	0x03, 0x09, 0x8D, 0x79, 0x76, 0x68, 0x04, 0x9D,
	0x48, 0x45, 0x69, 0x26, 0xAA, 0xDB, 0x89, 0x3B,
};

/* The ack prefix 6FDAD356-8165-4FDB-A4F2-B25C2B, reversed: on-air bytes 3..15. */
static const uint8_t ack_prefix_on_air[13] = {
	0x2B, 0x5C, 0xB2, 0xF2, 0xA4, 0xDB, 0x4F, 0x65, 0x81, 0x56, 0xD3, 0xDA, 0x6F,
};

uint8_t fob_battery_byte(int vdd_mv)
{
	if (vdd_mv <= 0) {
		return 0;
	}
	int units = (vdd_mv + 10) / 20;

	return units < 1 ? 1 : units > 255 ? 255 : (uint8_t)units;
}

void fob_press_mfg(uint8_t out[FOB_MFG_LEN], uint8_t fob_id, uint16_t counter, uint8_t battery)
{
	out[0] = FOB_COMPANY_ID & 0xFF;
	out[1] = FOB_COMPANY_ID >> 8;
	out[2] = FOB_PROTOCOL_VERSION;
	out[3] = fob_id;
	out[4] = counter & 0xFF;
	out[5] = counter >> 8;
	out[6] = battery;
}

bool fob_is_ack(const uint8_t *uuid, size_t len, uint8_t fob_id, uint16_t counter)
{
	return len == 16 && uuid[0] == (counter & 0xFF) && uuid[1] == (counter >> 8) &&
	       uuid[2] == fob_id && memcmp(&uuid[3], ack_prefix_on_air, sizeof(ack_prefix_on_air)) == 0;
}

bool fob_list_has_ack(const uint8_t *data, size_t len, uint8_t fob_id, uint16_t counter)
{
	for (size_t i = 0; i + 16 <= len; i += 16) {
		if (fob_is_ack(&data[i], 16, fob_id, counter)) {
			return true;
		}
	}
	return false;
}

uint8_t fob_id_from_pins(int bit0, int bit1, int bit2)
{
	return (uint8_t)((bit0 ? 0 : 1) | (bit1 ? 0 : 2) | (bit2 ? 0 : 4));
}
