/* Host unit tests for src/protocol.c, against docs/protocol.md §6's test vectors.
 * Plain C: Zephyr's native_sim doesn't run on macOS. Run with `make -C firmware/fob/tests`. */
#include <stdio.h>
#include <string.h>

#include "../src/protocol.h"

static int failures, checks;
#define CHECK(c) do { checks++; if (!(c)) { failures++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

/* Ack UUID for fob 3, counter 0x1234, as the fob receives it. */
static const uint8_t ack_3_1234[16] = {
	0x34, 0x12, 0x03, 0x2B, 0x5C, 0xB2, 0xF2, 0xA4, 0xDB, 0x4F, 0x65, 0x81, 0x56, 0xD3, 0xDA, 0x6F,
};

static void test_press_uuid(void)
{
	static const uint8_t want[16] = {0x03, 0x09, 0x8D, 0x79, 0x76, 0x68, 0x04, 0x9D,
					 0x48, 0x45, 0x69, 0x26, 0xAA, 0xDB, 0x89, 0x3B};
	CHECK(memcmp(fob_press_uuid, want, 16) == 0);
}

static void test_press_mfg_is_the_vector(void)
{
	uint8_t out[FOB_MFG_LEN];
	static const uint8_t want[FOB_MFG_LEN] = {0xFF, 0xFF, 0x01, 0x03, 0x34, 0x12, 0x96};

	fob_press_mfg(out, 3, 0x1234, 150);
	CHECK(memcmp(out, want, sizeof(want)) == 0);
}

static void test_battery_byte(void)
{
	CHECK(fob_battery_byte(3000) == 150);
	CHECK(fob_battery_byte(2209) == 110);
	CHECK(fob_battery_byte(2211) == 111);
	CHECK(fob_battery_byte(0) == 0);
	CHECK(fob_battery_byte(-5) == 0);
	CHECK(fob_battery_byte(3) == 1);
	CHECK(fob_battery_byte(9000) == 255);
}

static void test_ack_matches_only_its_press(void)
{
	CHECK(fob_is_ack(ack_3_1234, 16, 3, 0x1234));
	CHECK(!fob_is_ack(ack_3_1234, 16, 2, 0x1234));
	CHECK(!fob_is_ack(ack_3_1234, 16, 3, 0x1235));
	CHECK(!fob_is_ack(ack_3_1234, 16, 3, 0x3412));
	CHECK(!fob_is_ack(ack_3_1234, 15, 3, 0x1234));

	uint8_t bad[16];

	memcpy(bad, ack_3_1234, 16);
	bad[15] ^= 1;
	CHECK(!fob_is_ack(bad, 16, 3, 0x1234));
	CHECK(!fob_is_ack(fob_press_uuid, 16, 3, 0x1234));
}

static void test_ack_in_a_list(void)
{
	uint8_t list[48];

	memcpy(list, fob_press_uuid, 16);
	memset(&list[16], 0, 16);
	memcpy(&list[32], ack_3_1234, 16);
	CHECK(fob_list_has_ack(list, 48, 3, 0x1234));
	CHECK(!fob_list_has_ack(list, 32, 3, 0x1234));
	CHECK(!fob_list_has_ack(list, 47, 3, 0x1234));
	CHECK(!fob_list_has_ack(list, 0, 3, 0x1234));
}

static void test_id_from_pins(void)
{
	CHECK(fob_id_from_pins(1, 1, 1) == 0);
	CHECK(fob_id_from_pins(0, 1, 1) == 1);
	CHECK(fob_id_from_pins(1, 0, 1) == 2);
	CHECK(fob_id_from_pins(0, 0, 0) == 7);
	CHECK(fob_id_from_pins(0, 1, 0) == 5);
}

int main(void)
{
	test_press_uuid();
	test_press_mfg_is_the_vector();
	test_battery_byte();
	test_ack_matches_only_its_press();
	test_ack_in_a_list();
	test_id_from_pins();
	printf("%d checks, %d failures\n", checks, failures);
	return failures != 0;
}
