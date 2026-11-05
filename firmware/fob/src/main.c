/* iphone-remote fob firmware (IREM-6): one press, one advert burst, one ack.
 *
 * Idle: System ON sleep, waiting on the button's SENSE. A press reads the fob ID and VDD,
 * advertises the press for up to 300 ms and scans for the phone's ack for up to 2 s. A matching
 * ack stops both and flashes the LED once; no ack gives two short flashes. Protocol:
 * docs/protocol.md (IREM-2); behaviour: the design doc's §7. */
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gap.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/util.h>

#include "protocol.h"

#define FOB_NODE DT_PATH(fob)

/* Timing, docs/protocol.md §5. */
#define ADV_INTERVAL 0x20		/* 20 ms, in 0.625 ms units */
#define SCAN_INTERVAL 0x60		/* 60 ms */
#define SCAN_WINDOW 0x30		/* 30 ms: 50% duty */
#define BURST_MS 300
#define LISTEN_MS 2000
#define LISTEN_LOW_MS 1000		/* a tired cell listens for less... */
#define LOW_MV 2200			/* ...below this, and skips the LED */
#define RELEASE_MS 30			/* the button counts as released after this long quiet */
#define ACK_FLASH_MS 50
#define MISS_FLASH_MS 15
#define MISS_GAP_MS 120

static const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(FOB_NODE, button_gpios);
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(FOB_NODE, led_gpios);
static const struct gpio_dt_spec id_pins[3] = {
	GPIO_DT_SPEC_GET_BY_IDX(FOB_NODE, id_gpios, 0),
	GPIO_DT_SPEC_GET_BY_IDX(FOB_NODE, id_gpios, 1),
	GPIO_DT_SPEC_GET_BY_IDX(FOB_NODE, id_gpios, 2),
};
static const struct adc_dt_spec vdd_channel = ADC_DT_SPEC_GET(FOB_NODE);

/* Everything below runs on this queue, so the press state needs no lock; the scan callback
 * (the Bluetooth RX thread) only reads it to match an ack, then hands over to the queue. */
K_THREAD_STACK_DEFINE(fob_stack, 1024);
static struct k_work_q fob_q;

static struct {
	uint16_t counter;
	uint8_t fob_id;
	bool low;
} press;
/* Set while a press is waiting for its ack (the value of press.counter, plus 1, so 0 = none). */
static atomic_t listening_for;

static bool held;	/* the button is down (debounced release) */

static uint8_t mfg[FOB_MFG_LEN];
static const struct bt_data ad[] = {
	BT_DATA(BT_DATA_UUID128_ALL, fob_press_uuid, 16),
	BT_DATA(BT_DATA_MANUFACTURER_DATA, mfg, sizeof(mfg)),
};

static void press_work_fn(struct k_work *w);
static void burst_end_fn(struct k_work *w);
static void listen_end_fn(struct k_work *w);
static void acked_fn(struct k_work *w);
static void release_check_fn(struct k_work *w);
static K_WORK_DEFINE(press_work, press_work_fn);
static K_WORK_DEFINE(acked_work, acked_fn);
static K_WORK_DELAYABLE_DEFINE(burst_end, burst_end_fn);
static K_WORK_DELAYABLE_DEFINE(listen_end, listen_end_fn);
static K_WORK_DELAYABLE_DEFINE(release_check, release_check_fn);

static uint8_t read_fob_id(void)
{
	int v[3];

	for (int i = 0; i < 3; i++) {
		gpio_pin_configure_dt(&id_pins[i], GPIO_INPUT | GPIO_PULL_UP);
	}
	k_busy_wait(20);
	for (int i = 0; i < 3; i++) {
		v[i] = gpio_pin_get_raw(id_pins[i].port, id_pins[i].pin);
		gpio_pin_configure_dt(&id_pins[i], GPIO_DISCONNECTED);
	}
	return fob_id_from_pins(v[0], v[1], v[2]);
}

/* VDD in mV, or 0 if it couldn't be read. */
static int read_vdd_mv(void)
{
	int16_t raw;
	struct adc_sequence seq = {.buffer = &raw, .buffer_size = sizeof(raw)};

	if (adc_sequence_init_dt(&vdd_channel, &seq) || adc_read_dt(&vdd_channel, &seq)) {
		return 0;
	}
	int32_t mv = raw;

	return adc_raw_to_millivolts_dt(&vdd_channel, &mv) ? 0 : mv;
}

static void flash(int times, int on_ms, int gap_ms)
{
	for (int i = 0; i < times; i++) {
		if (i) {
			k_msleep(gap_ms);
		}
		gpio_pin_set_dt(&led, 1);
		k_msleep(on_ms);
		gpio_pin_set_dt(&led, 0);
	}
}

static void stop_radio(void)
{
	bt_le_adv_stop();
	bt_le_scan_stop();
}

static bool ad_has_ack(struct bt_data *data, void *user)
{
	bool *found = user;

	if ((data->type == BT_DATA_UUID128_ALL || data->type == BT_DATA_UUID128_SOME) &&
	    fob_list_has_ack(data->data, data->data_len, press.fob_id, press.counter)) {
		*found = true;
		return false;
	}
	return true;
}

static void scanned(const bt_addr_le_t *addr, int8_t rssi, uint8_t type, struct net_buf_simple *buf)
{
	bool found = false;

	if (atomic_get(&listening_for) != press.counter + 1) {
		return;
	}
	bt_data_parse(buf, ad_has_ack, &found);
	if (found) {
		k_work_submit_to_queue(&fob_q, &acked_work);
	}
}

static void press_work_fn(struct k_work *w)
{
	/* VDD first, before the radio loads the cell. */
	int mv = read_vdd_mv();

	stop_radio();
	press.counter++;
	press.fob_id = read_fob_id();
	press.low = mv > 0 && mv < LOW_MV;
	fob_press_mfg(mfg, press.fob_id, press.counter, fob_battery_byte(mv));
	atomic_set(&listening_for, press.counter + 1);

	static const struct bt_le_adv_param adv = BT_LE_ADV_PARAM_INIT(0, ADV_INTERVAL, ADV_INTERVAL, NULL);
	static const struct bt_le_scan_param scan = {
		.type = BT_LE_SCAN_TYPE_PASSIVE,
		.interval = SCAN_INTERVAL,
		.window = SCAN_WINDOW,
	};

	bt_le_adv_start(&adv, ad, ARRAY_SIZE(ad), NULL, 0);
	bt_le_scan_start(&scan, scanned);
	k_work_reschedule_for_queue(&fob_q, &burst_end, K_MSEC(BURST_MS));
	k_work_reschedule_for_queue(&fob_q, &listen_end, K_MSEC(press.low ? LISTEN_LOW_MS : LISTEN_MS));
}

static void burst_end_fn(struct k_work *w)
{
	bt_le_adv_stop();
}

static void listen_end_fn(struct k_work *w)
{
	if (atomic_set(&listening_for, 0) == 0) {
		return;
	}
	stop_radio();
	if (!press.low) {
		flash(2, MISS_FLASH_MS, MISS_GAP_MS);	/* "the phone didn't hear" */
	}
}

static void acked_fn(struct k_work *w)
{
	if (atomic_set(&listening_for, 0) == 0) {
		return;	/* a second ack advert for the same press, or a late one */
	}
	stop_radio();
	k_work_cancel_delayable(&burst_end);
	k_work_cancel_delayable(&listen_end);
	if (!press.low) {
		flash(1, ACK_FLASH_MS, 0);
	}
}

/* The first edge of a press acts at once; the release counts once the pin has been quiet and
 * high for RELEASE_MS, so contact bounce on either edge never makes a second press. */
static void release_check_fn(struct k_work *w)
{
	if (gpio_pin_get_dt(&button) == 0) {
		held = false;
	}
}

static void button_edge(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	if (!held && gpio_pin_get_dt(&button) == 1) {
		held = true;
		k_work_submit_to_queue(&fob_q, &press_work);
	}
	k_work_reschedule_for_queue(&fob_q, &release_check, K_MSEC(RELEASE_MS));
}

static struct gpio_callback button_cb;

int main(void)
{
	k_work_queue_start(&fob_q, fob_stack, K_THREAD_STACK_SIZEOF(fob_stack), K_PRIO_PREEMPT(5), NULL);

	gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE);
	for (int i = 0; i < 3; i++) {
		gpio_pin_configure_dt(&id_pins[i], GPIO_DISCONNECTED);
	}
	adc_channel_setup_dt(&vdd_channel);

	if (bt_enable(NULL)) {
		flash(5, 200, 200);	/* can't start the radio: nothing else will work */
		return 0;
	}
	/* A fresh cell must not repeat the counter the phone saw last (docs/protocol.md §2). */
	sys_rand_get(&press.counter, sizeof(press.counter));

	gpio_pin_configure_dt(&button, GPIO_INPUT);
	gpio_init_callback(&button_cb, button_edge, BIT(button.pin));
	gpio_add_callback_dt(&button, &button_cb);
	gpio_pin_interrupt_configure_dt(&button, GPIO_INT_EDGE_BOTH);

	flash(1, 20, 0);	/* alive */
	return 0;
}
