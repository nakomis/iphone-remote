# Fob emulator (IREM-8)

An ESP32-S3 that behaves like an iphone-remote fob on air, for answering the iPhone questions in
[`docs/protocol.md` §7](../../docs/protocol.md#7-to-prove-on-the-first-real-fob) before real fobs
exist.

- It sends exactly the fob's version 1 press advert: 27 bytes, no flags AD, non-connectable,
  20 ms, random static address. It's built by the real firmware's `fob/src/protocol.c`, so it
  can't drift from it.
- It listens for the ack the way the fob does: passively, 30 ms in every 60 ms, for up to 2 s.
- It reports the press-to-ack latency, whether the ack came in the main advert packet, and the
  raw ack advert.
- Unlike the fob, it keeps listening for 600 ms after the first ack, at 100% duty, and counts the
  ack's packets. That shows how often the phone advertises and for how long.

Any ESP32-S3 board works. Press with **BOOT** or a key on the serial console.

## Build and flash

ESP-IDF v5.5:

```bash
cd firmware/fob-emulator
. ~/esp/esp-idf/export.sh
idf.py set-target esp32s3     # once
idf.py -p /dev/cu.usbmodem1101 build flash
```

If the board stays in download mode after flashing, start it with
`python -m esptool --chip esp32s3 -p /dev/cu.usbmodem1101 --before no_reset --after watchdog_reset chip_id`.

## Console

Open it with `idf.py -p /dev/cu.usbmodem1101 monitor`, or any serial terminal on the
USB-Serial-JTAG port. Each key acts on its own, with no Enter needed.

| Key | |
|---|---|
| `p` or BOOT | Press |
| `a` | Auto-press every 3 s, on or off |
| `0`–`7` | Set the fob ID (the default is 3) |
| `m` | Monitor: count every ack packet for 5 s at 100% duty. Use it with a phone holding one ack on air, to measure the phone's advertising interval |
| `s` | Summary: the share of presses acked, the latency spread, and the ack packets per press |
| `r` | Reset the summary |
| `v` | Verbose (the raw ack advert, and the arrival time of every ack packet) |

A press, verbose:

```
fob 3 #7411: ack after 29 ms, 1 ack packet(s) over 0 ms, RSSI -48
  first ack came in a primary advert
  ack advert: 02 01 1A 11 07 F3 1C 03 2B 5C B2 F2 A4 DB 4F 65 81 56 D3 DA 6F
  heard at (ms): 29
```

## Testing with an iPhone

Run ScreenEye (the EYE-10 branch of `nakomis/mcps`) on screen, with the key fob turned on in
Settings. Then, on the emulator:

1. Press `v` (verbose off), `r`, then `a`. Leave it for a minute or two, then press `a` and `s`.
2. Read off the §7 answers:
   - **§7.1** (iOS reports the press advert): ScreenEye counts each press.
   - **§7.2** (the ack is in the main advert packet): verbose shows "primary advert".
   - **§7.3** (latency): the summary's latency line.
   - **§7.4** (150 ms is long enough): the share acked, and the packets per ack. If the phone
     advertises every *I* ms, a 150 ms ack holds about 150 / *I* packets, and the fob, listening
     half the time, catches each one with a probability of about one half.

## The Mac as the phone

`tools/phone.swift` stands in for the phone on a Mac. It acks presses exactly as protocol.md §3
and §4 say, and as ScreenEye's `KeyFob.swift` does. It proves the round trip, but macOS isn't
iOS, so its timings say nothing about an iPhone.

```bash
swift firmware/fob-emulator/tools/phone.swift          # ack presses
swift firmware/fob-emulator/tools/phone.swift --hold   # hold one ack on air, for `m`
```

The terminal running it needs Bluetooth permission.

### Results with the Mac (6 November 2026)

- The round trip works. The press is decoded, and the ack comes back in the main advert packet
  (`02 01 1A` flags, then the ack UUID: 21 bytes, as §3 predicts).
- **macOS advertises about every 182 ms** (`m` with `--hold`: 22 packets in 5 s, a median gap
  of 187 ms). A 150 ms ack therefore holds at most one packet, and often none. Only about 40% of
  presses were acked (7 of 17 and 8 of 20 in two runs), and never with more than one packet.
  When an ack arrived, it came 26–274 ms after the press (a median of about 70 ms).
- If an iPhone in the foreground advertises as slowly, the protocol needs a change. One option is
  a longer ack on the phone (only the app changes). Another is for the fob to listen full-time
  for the 2 s, which costs battery.
