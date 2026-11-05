# Fob firmware (IREM-6)

nRF Connect SDK (Zephyr) application for the fob, `fob/`. It speaks the protocol in
[`docs/protocol.md`](../docs/protocol.md) and behaves as the design doc's §7 says.

- **Idle:** System ON sleep, waiting on the button's SENSE, with the LFCLK on the RC
  oscillator and the DC/DC on.
- **On a press:**
  1. Read VDD and the ID jumpers.
  2. Advertise the press for 300 ms at 20 ms intervals, and scan at 50% duty for up to 2 s
     for the ack.
  3. An ack gives one 50 ms flash; no ack gives two short flashes.
  4. Below 2.2 V there are no flashes, and the scan stops after 1 s.

## Layout

| Path | What |
|---|---|
| `fob/src/protocol.[ch]` | The protocol: advert payload, ack matching, jumper decoding. No Zephyr, host-tested |
| `fob/src/main.c` | The application |
| `fob/boards/nakomis/iphone_remote_fob/` | The fob as a Zephyr board (nRF52810, pins from `hardware/fob/board/fob_board.py`) |
| `fob/boards/promicro_nrf52840_nrf52840_uf2.overlay` | Development on a Pro Micro nRF52840 |
| `fob/dts/bindings/` | The `fob` devicetree node: button, LED, ID jumpers, VDD channel |
| `fob/tests/` | Host unit tests for `protocol.c` |

## Setting up (macOS)

NCS v3.4.2 and Zephyr SDK 1.0.1 (arm only), installed by `~/ncs/setup.sh`:

```sh
source ~/ncs/.venv/bin/activate
cd ~/ncs/v3.4.2
```

## Building

```sh
# The fob
west build -p --no-sysbuild -b iphone_remote_fob -d build/fob ~/repos/nakomis/iphone-remote/firmware/fob

# A Pro Micro nRF52840, for development (makes zephyr.uf2)
west build -p --no-sysbuild -b promicro_nrf52840/nrf52840/uf2 -d build/promicro ~/repos/nakomis/iphone-remote/firmware/fob
```

`--no-sysbuild` because there's no bootloader to build, and so sysbuild doesn't need to know
about the app's own board. Sizes on 5 Nov 2026: the fob image is 110,712 B of 192 KB flash
(56%) and 19,120 B of 24 KB RAM (78%), with the SoftDevice Controller (multirole library).

The Pro Micro uses its UF2 bootloader. Double-tap reset, then copy
`build/promicro/zephyr/zephyr.uf2` onto the drive that appears. Wire:

- a button from P0.17 to GND;
- optionally, ID jumpers from P0.20, P0.22 and P0.24 to GND (all open is fob 0).

The LED is the board's own, on P0.15.

## Tests

```sh
make -C firmware/fob/tests            # 25 checks against docs/protocol.md §6's test vectors
make -C firmware/fob/tests coverage   # line coverage of protocol.c (gcov)
```

They're plain C rather than ztest, because `native_sim` doesn't run on macOS.

## Flashing the fob over SWD, with a Raspberry Pi

The cable is a TC2030-IDC-NL (a 6-pin 2.54 mm IDC socket). The fob's TC2030 pads have no
leg holes, so hold the plug in place by hand while it flashes. Wire the IDC socket to the
Pi's header:

| TC2030 / IDC pin | Signal | Pi physical pin |
|---|---|---|
| 1 | VBAT | 1 (3V3): **only with no CR2032 fitted, never both** |
| 2 | SWDIO | 18 (GPIO24) |
| 3 | nRESET | 12 (GPIO18), optional |
| 4 | SWDCLK | 22 (GPIO25) |
| 5 | GND | 20 |
| 6 | SWO | not connected |

On the Pi, install OpenOCD (0.12 or later, which has `linuxgpiod`), then:

```sh
cat > fob.cfg <<'EOF'
adapter driver linuxgpiod
adapter gpio swclk 25 -chip 0
adapter gpio swdio 24 -chip 0
adapter gpio srst 18 -chip 0
transport select swd
adapter speed 1000
source [find target/nrf52.cfg]
EOF
```

On a Pi 5 the header's GPIOs are on `gpiochip4` on older kernels and `gpiochip0` on newer
ones; `gpioinfo` tells you which.

- **First time, every new chip:** the nRF52810 ships with APPROTECT on, so the first
  connection needs a recover. Recover erases the chip.

  ```sh
  openocd -f fob.cfg -c "init; nrf52_recover; exit"
  ```

- **Flashing:** copy `build/fob/zephyr/zephyr.hex` to the Pi, then:

  ```sh
  openocd -f fob.cfg -c "init; reset halt; nrf5 mass_erase; program zephyr.hex verify; reset run; exit"
  ```

  The LED flashes once (20 ms) when the firmware has started.

Rehearse on the Holyiot nRF52810 beacon first: it has the same chip.
