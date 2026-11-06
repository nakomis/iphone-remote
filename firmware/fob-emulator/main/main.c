/* iphone-remote fob emulator (IREM-8): an ESP32-S3 that sends exactly the fob's version 1
 * press advert (docs/protocol.md §2, built by the real firmware's protocol.c), listens for the
 * phone's ack the way the fob does (passive, 30 ms every 60 ms), and reports what it heard over
 * the serial console. It's for proving protocol.md §7 against a real iPhone before the fobs
 * exist.
 *
 * Unlike the fob, it keeps listening for a while after the first ack, at 100% duty, so it can
 * say how long the phone advertised the ack for and how often (§7.4). The latency to the first
 * ack is measured at the fob's own 50% duty, so it's what a real fob would see.
 *
 * Press with the BOOT button or a key on the console; see help() for the keys. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "host/ble_hs.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "nvs_flash.h"
#include "protocol.h"

#define BUTTON_GPIO GPIO_NUM_0	/* BOOT on every ESP32-S3 dev board */
#define ADV_ITVL 32		/* 20 ms, in 0.625 ms units (protocol.md §5) */
#define SCAN_ITVL 96		/* 60 ms */
#define SCAN_WINDOW 48		/* 30 ms: 50% duty, as the fob */
#define BURST_MS 300
#define LISTEN_MS 2000
#define SURVEY_MS 600		/* listening after the first ack, to see the whole ack */
#define AUTO_MS 3000
#define MONITOR_MS 5000
#define BATTERY 150		/* 3.00 V, so the phone shows something plausible */
#define MAX_RESULTS 512
#define MAX_HEARD 400

static const char *TAG = "fob";

/* Shared between the NimBLE host task (scan callback) and the press task. */
static portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
static struct {
	bool listening;
	bool monitor;			/* record every ack-prefix packet, whatever its fob */
	uint8_t fob_id;
	uint16_t counter;
	int64_t t0;			/* µs, when the press started */
	int heard;			/* matching ack packets */
	int64_t at[MAX_HEARD];		/* µs since t0 */
	int8_t rssi;
	uint8_t first_adv[31];		/* the first matching advert, raw */
	uint8_t first_len;
	uint8_t first_type;		/* HCI advert report event type */
	int foreign;			/* ack-prefix UUIDs for another fob or counter */
	uint8_t foreign_id;
	uint16_t foreign_ctr;
} st;

static uint8_t fob_id = 3;
static uint16_t counter;
static bool auto_press;
static bool verbose = true;
static bool connectable_fallback;
static SemaphoreHandle_t press_sem;
static volatile bool monitor_req;

/* Results, for the summary. -1 = no ack. */
static int latency_ms[MAX_RESULTS];
static int ack_packets[MAX_RESULTS];
static int ack_span_ms[MAX_RESULTS];
static int results;

/* The ack prefix, on-air order (protocol.md §3): on-air bytes 3..15. */
static const uint8_t ack_prefix_on_air[13] = {
	0x2B, 0x5C, 0xB2, 0xF2, 0xA4, 0xDB, 0x4F, 0x65, 0x81, 0x56, 0xD3, 0xDA, 0x6F,
};

static void hex(const char *label, const uint8_t *b, int n)
{
	printf("%s", label);
	for (int i = 0; i < n; i++) {
		printf(" %02X", b[i]);
	}
	printf("\n");
}

static int gap_event(struct ble_gap_event *event, void *arg)
{
	switch (event->type) {
	case BLE_GAP_EVENT_DISC: {
		const struct ble_gap_disc_desc *d = &event->disc;
		int64_t now = esp_timer_get_time();

		for (int i = 0; i + 1 < d->length_data;) {
			int len = d->data[i];
			if (len == 0 || i + 1 + len > d->length_data) {
				break;
			}
			uint8_t type = d->data[i + 1];
			const uint8_t *v = &d->data[i + 2];
			int vlen = len - 1;

			if (type == 0x06 || type == 0x07) {
				for (int u = 0; u + 16 <= vlen; u += 16) {
					const uint8_t *uuid = &v[u];
					if (memcmp(&uuid[3], ack_prefix_on_air, 13) != 0) {
						continue;
					}
					portENTER_CRITICAL(&lock);
					if (st.monitor) {
						if (st.heard < MAX_HEARD) {
							st.at[st.heard] = now - st.t0;
						}
						st.heard++;
					} else if (st.listening && fob_is_ack(uuid, 16, st.fob_id, st.counter)) {
						if (st.heard == 0) {
							st.rssi = d->rssi;
							st.first_len = d->length_data;
							st.first_type = d->event_type;
							memcpy(st.first_adv, d->data, d->length_data);
						}
						if (st.heard < MAX_HEARD) {
							st.at[st.heard] = now - st.t0;
						}
						st.heard++;
					} else if (st.listening) {
						st.foreign++;
						st.foreign_id = uuid[2];
						st.foreign_ctr = uuid[0] | uuid[1] << 8;
					}
					portEXIT_CRITICAL(&lock);
				}
			}
			i += 1 + len;
		}
		return 0;
	}
	case BLE_GAP_EVENT_CONNECT:
		/* Only reachable in the connectable fallback: the fob refuses every connection. */
		if (event->connect.status == 0) {
			ble_gap_terminate(event->connect.conn_handle, BLE_ERR_REM_USER_CONN_TERM);
		}
		return 0;
	default:
		return 0;
	}
}

static int start_adv(void)
{
	uint8_t ad[27];
	uint8_t mfg[FOB_MFG_LEN];

	fob_press_mfg(mfg, st.fob_id, st.counter, BATTERY);
	ad[0] = 0x11;
	ad[1] = 0x07;
	memcpy(&ad[2], fob_press_uuid, 16);
	ad[18] = 0x08;
	ad[19] = 0xFF;
	memcpy(&ad[20], mfg, FOB_MFG_LEN);

	int rc = ble_gap_adv_set_data(ad, sizeof(ad));
	if (rc) {
		ESP_LOGE(TAG, "adv_set_data: %d", rc);
		return rc;
	}
	if (verbose && results == 0) {
		hex("press advert:", ad, sizeof(ad));
	}
	struct ble_gap_adv_params p = {
		.conn_mode = connectable_fallback ? BLE_GAP_CONN_MODE_UND : BLE_GAP_CONN_MODE_NON,
		.disc_mode = BLE_GAP_DISC_MODE_NON,
		.itvl_min = ADV_ITVL,
		.itvl_max = ADV_ITVL,
	};
	rc = ble_gap_adv_start(BLE_OWN_ADDR_RANDOM, NULL, BLE_HS_FOREVER, &p, gap_event, NULL);
	if (rc && !connectable_fallback) {
		ESP_LOGW(TAG, "non-connectable advertising at 20 ms refused (%d); using ADV_IND", rc);
		connectable_fallback = true;
		p.conn_mode = BLE_GAP_CONN_MODE_UND;
		rc = ble_gap_adv_start(BLE_OWN_ADDR_RANDOM, NULL, BLE_HS_FOREVER, &p, gap_event, NULL);
	}
	if (rc) {
		ESP_LOGE(TAG, "adv_start: %d", rc);
	}
	return rc;
}

static int start_scan(uint16_t window)
{
	struct ble_gap_disc_params p = {
		.itvl = SCAN_ITVL,
		.window = window,
		.passive = 1,
		.filter_duplicates = 0,
	};
	int rc = ble_gap_disc(BLE_OWN_ADDR_RANDOM, BLE_HS_FOREVER, &p, gap_event, NULL);
	if (rc) {
		ESP_LOGE(TAG, "disc: %d", rc);
	}
	return rc;
}

static void record(int latency, int packets, int span)
{
	if (results < MAX_RESULTS) {
		latency_ms[results] = latency;
		ack_packets[results] = packets;
		ack_span_ms[results] = span;
		results++;
	}
}

static void press(void)
{
	counter++;
	portENTER_CRITICAL(&lock);
	memset(&st, 0, sizeof(st));
	st.fob_id = fob_id;
	st.counter = counter;
	st.t0 = esp_timer_get_time();
	st.listening = true;
	portEXIT_CRITICAL(&lock);

	if (start_adv() || start_scan(SCAN_WINDOW)) {
		ble_gap_adv_stop();
		ble_gap_disc_cancel();
		st.listening = false;
		return;
	}

	bool advertising = true;
	bool full_duty = false;
	int64_t first = -1;
	for (;;) {
		vTaskDelay(pdMS_TO_TICKS(5));
		int64_t t = (esp_timer_get_time() - st.t0) / 1000;
		portENTER_CRITICAL(&lock);
		int heard = st.heard;
		if (heard && first < 0) {
			first = st.at[0] / 1000;
		}
		portEXIT_CRITICAL(&lock);
		/* Like the fob: stop the press as soon as it's acked, or after the burst. */
		if (advertising && (heard || t >= BURST_MS)) {
			ble_gap_adv_stop();
			advertising = false;
		}
		/* The fob would sleep now. Listen full-time instead, so the packet count measures
		 * the phone's advertising interval rather than our duty cycle. */
		if (heard && !full_duty) {
			ble_gap_disc_cancel();
			start_scan(SCAN_ITVL);
			full_duty = true;
		}
		if (first >= 0 ? t >= first + SURVEY_MS : t >= LISTEN_MS) {
			break;
		}
	}
	ble_gap_disc_cancel();
	portENTER_CRITICAL(&lock);
	st.listening = false;
	portEXIT_CRITICAL(&lock);

	if (!st.heard) {
		printf("fob %u #%u: no ack in %d ms", st.fob_id, st.counter, LISTEN_MS);
		if (st.foreign) {
			printf(" (but %d ack(s) for something else, last fob %u #%u)", st.foreign,
			       st.foreign_id, st.foreign_ctr);
		}
		printf("\n");
		record(-1, 0, 0);
		return;
	}

	int n = st.heard < MAX_HEARD ? st.heard : MAX_HEARD;
	int lat = (int)(st.at[0] / 1000);
	int span = (int)((st.at[n - 1] - st.at[0]) / 1000);
	int min_gap = 0;
	for (int i = 1; i < n; i++) {
		int gap = (int)((st.at[i] - st.at[i - 1]) / 1000);
		if (i == 1 || gap < min_gap) {
			min_gap = gap;
		}
	}
	printf("fob %u #%u: ack after %d ms, %d ack packet(s) over %d ms", st.fob_id, st.counter,
	       lat, st.heard, span);
	if (n > 1) {
		printf(", shortest gap %d ms", min_gap);
	}
	printf(", RSSI %d\n", st.rssi);
	if (verbose) {
		printf("  first ack came in a %s\n",
		       st.first_type == BLE_HCI_ADV_RPT_EVTYPE_SCAN_RSP ? "scan response" : "primary advert");
		hex("  ack advert:", st.first_adv, st.first_len);
		printf("  heard at (ms):");
		for (int i = 0; i < n; i++) {
			printf(" %d", (int)(st.at[i] / 1000));
		}
		printf("\n");
	}
	record(lat, st.heard, span);
}

static int cmp_int(const void *a, const void *b);

/* Listens with a 100% duty scan for MONITOR_MS and reports every ack-prefix packet: with the
 * phone holding one ack on air, that's the phone's advertising interval. */
static void monitor(void)
{
	portENTER_CRITICAL(&lock);
	memset(&st, 0, sizeof(st));
	st.t0 = esp_timer_get_time();
	st.monitor = true;
	portEXIT_CRITICAL(&lock);
	struct ble_gap_disc_params p = {
		.itvl = SCAN_ITVL, .window = SCAN_ITVL, .passive = 1, .filter_duplicates = 0,
	};
	if (ble_gap_disc(BLE_OWN_ADDR_RANDOM, BLE_HS_FOREVER, &p, gap_event, NULL)) {
		printf("monitor: scan refused\n");
		return;
	}
	vTaskDelay(pdMS_TO_TICKS(MONITOR_MS));
	ble_gap_disc_cancel();
	portENTER_CRITICAL(&lock);
	st.monitor = false;
	portEXIT_CRITICAL(&lock);

	int n = st.heard < MAX_HEARD ? st.heard : MAX_HEARD;
	printf("monitor: %d ack packet(s) in %d ms", st.heard, MONITOR_MS);
	if (n > 1) {
		static int gaps[MAX_HEARD];
		for (int i = 1; i < n; i++) {
			gaps[i - 1] = (int)((st.at[i] - st.at[i - 1]) / 1000);
		}
		qsort(gaps, n - 1, sizeof(int), cmp_int);
		printf(", gaps ms: min %d, median %d, max %d", gaps[0], gaps[(n - 1) / 2], gaps[n - 2]);
	}
	printf("\n");
}

static int cmp_int(const void *a, const void *b)
{
	return *(const int *)a - *(const int *)b;
}

static void summary(void)
{
	static int sorted[MAX_RESULTS];
	int acked = 0, packets = 0, spans = 0;

	for (int i = 0; i < results; i++) {
		if (latency_ms[i] >= 0) {
			sorted[acked++] = latency_ms[i];
			packets += ack_packets[i];
			spans += ack_span_ms[i];
		}
	}
	printf("%d press(es), %d acked (%d%%)\n", results, acked, results ? 100 * acked / results : 0);
	if (!acked) {
		return;
	}
	qsort(sorted, acked, sizeof(int), cmp_int);
	printf("ack latency ms: min %d, median %d, 90th %d, max %d\n", sorted[0], sorted[acked / 2],
	       sorted[(acked * 9) / 10 < acked ? (acked * 9) / 10 : acked - 1], sorted[acked - 1]);
	printf("per ack: mean %.1f packet(s) over a mean %d ms\n", (double)packets / acked,
	       spans / acked);
}

static void help(void)
{
	printf("\niphone-remote fob emulator (IREM-8): fob %u, next counter %u\n"
	       "  p or BOOT  press\n"
	       "  a          auto-press every %d s (now %s)\n"
	       "  0-7        set the fob ID\n"
	       "  m          monitor: count ack packets for %d s at 100%% duty (phone's interval)\n"
	       "  s          summary of every press so far\n"
	       "  r          reset the summary\n"
	       "  v          verbose (now %s)\n"
	       "  h          this help\n\n",
	       fob_id, (uint16_t)(counter + 1), AUTO_MS / 1000, auto_press ? "on" : "off", MONITOR_MS / 1000,
	       verbose ? "on" : "off");
}

static void press_task(void *arg)
{
	for (;;) {
		bool go = xSemaphoreTake(press_sem, pdMS_TO_TICKS(AUTO_MS)) == pdTRUE;
		if (monitor_req) {
			monitor_req = false;
			monitor();
		} else if (go || auto_press) {
			press();
		}
	}
}

static void console_task(void *arg)
{
	for (;;) {
		int c = fgetc(stdin);
		if (c == EOF) {
			vTaskDelay(pdMS_TO_TICKS(20));
			continue;
		}
		switch (c) {
		case 'p':
			xSemaphoreGive(press_sem);
			break;
		case 'a':
			auto_press = !auto_press;
			printf("auto-press %s\n", auto_press ? "on" : "off");
			break;
		case 'm':
			monitor_req = true;
			xSemaphoreGive(press_sem);
			break;
		case 's':
			summary();
			break;
		case 'r':
			results = 0;
			printf("summary reset\n");
			break;
		case 'v':
			verbose = !verbose;
			printf("verbose %s\n", verbose ? "on" : "off");
			break;
		case 'h':
		case '?':
			help();
			break;
		default:
			if (c >= '0' && c <= '7') {
				fob_id = c - '0';
				printf("fob ID %u\n", fob_id);
			}
		}
	}
}

static void button_task(void *arg)
{
	gpio_config_t io = {
		.pin_bit_mask = 1ULL << BUTTON_GPIO,
		.mode = GPIO_MODE_INPUT,
		.pull_up_en = GPIO_PULLUP_ENABLE,
	};
	gpio_config(&io);
	int was = 1;
	for (;;) {
		vTaskDelay(pdMS_TO_TICKS(10));
		int now = gpio_get_level(BUTTON_GPIO);
		if (was && !now) {
			xSemaphoreGive(press_sem);
		}
		was = now;
	}
}

static void synced(void)
{
	ble_addr_t addr;
	/* A random static address, as the fob uses. */
	if (ble_hs_id_gen_rnd(0, &addr) == 0 && ble_hs_id_set_rnd(addr.val) == 0) {
		printf("random static address %02X:%02X:%02X:%02X:%02X:%02X\n", addr.val[5],
		       addr.val[4], addr.val[3], addr.val[2], addr.val[1], addr.val[0]);
	}
	help();
}

static void host_task(void *arg)
{
	nimble_port_run();
	nimble_port_freertos_deinit();
}

void app_main(void)
{
	esp_err_t err = nvs_flash_init();
	if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
		nvs_flash_erase();
		nvs_flash_init();
	}

	usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
	usb_serial_jtag_driver_install(&cfg);
	usb_serial_jtag_vfs_use_driver();
	setvbuf(stdin, NULL, _IONBF, 0);

	/* Seeded from the RNG at power-up, as the fob does. */
	counter = (uint16_t)esp_random();
	press_sem = xSemaphoreCreateBinary();

	ESP_ERROR_CHECK(nimble_port_init());
	ble_hs_cfg.sync_cb = synced;
	nimble_port_freertos_init(host_task);

	xTaskCreate(press_task, "press", 4096, NULL, 5, NULL);
	xTaskCreate(console_task, "console", 4096, NULL, 4, NULL);
	xTaskCreate(button_task, "button", 4096, NULL, 4, NULL);
}
