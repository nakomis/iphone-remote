# iphone-remote: trigger fob design

- **Date:** 5 November 2026
- **Plane:** IREM-1 (this document), IREM-2 (protocol, drafted in §6)
- **Status:** draft, awaiting Martin's approval

Items marked **[Claude's call]** were decided by Claude without Martin's input;
they're open to change. Everything else was agreed with Martin.

## 1. Intent

Martin has written his own iPhone camera app. He wants a small handheld remote
to fire its shutter: a fob the size of a car key, with one button, used about
6 ft (2 m) from the phone, on subjects that don't move. A press must take
effect well under a second later.

An LED on the fob flashes when the phone has **received and understood** the
press. It doesn't mean the photo has been taken.

Several fobs can talk to one phone; each has a solder-jumper ID.

**Operating envelope [Claude's call]:** indoors, roughly 10–35 °C; must
send presses down to 2.0 V cell voltage.

## 2. Goals, non-goals, anti-goals

**Goals**

- Press-to-callback latency in the tens of milliseconds; under ~100 ms worst case.
- Runs for years on one CR2032.
- No pairing, no setup: put a cell in and it works.
- Assembled by JLCPCB **Economic** PCBA. This is a hard cost constraint; Standard
  costs much more.
- Up to 8 fobs per phone, distinguished by ID.
- A per-press ack LED.
- Spare GPIOs brought out to an unpopulated header for future use.

**Non-goals (for now)**

- The iPhone-side code. Martin will add it to his app against the protocol in §6.
- The case. Martin designs it from the board outline this project exports.
- Firmware beyond a placeholder item (IREM-6), except the size check in §9.
- Security against deliberate replay or spoofing. A camera trigger doesn't need it.

**Anti-goals: failures even if it technically works**

- Any part or rule that pushes the order from Economic to Standard PCBA.
- A sleep current that turns "years" into "months".
- Needing to pair, or a phone-side Bluetooth setup step.
- A fob that triggers a different fob's ack, or one press firing two captures.

## 3. Constraints

### JLCPCB Economic PCBA (from jlcpcb.com/capabilities/pcb-assembly-capabilities, Nov 2026)

- Parts on **one side only** (SMT and THT both allowed).
- 2, 4 or 6 layers, standard stackup only; 0.8–1.6 mm thick.
- Smallest package 0402; minimum IC pin pitch 0.4 mm; minimum BGA pitch 0.5 mm.
- No castellated holes, gold fingers or edge plating; mouse-bite panels only.
- 2–50 boards per order.
- Every BOM part must be in stock and listed as **"Economic and Standard"** on
  its JLC part page. Some parts are "Standard only" and would force Standard.
- Each *extended* (non-basic) part adds a one-off feeder fee per order, so
  keep the number of unique extended parts down.

### Power

CR2032, about 220 mAh nominal, with high internal resistance. Short current
peaks of a few mA are fine with a bulk capacitor; tens of mA are not. Over 10
years the cell loses 1–2% a year to self-discharge, which bounds battery life
whatever the fob does.

### iOS (affects the protocol)

- A foreground app can scan for adverts, including non-connectable ones, and
  can read their manufacturer data.
- An app can only **advertise** a local name and a list of service UUIDs: no
  manufacturer or service data. So the ack must be encoded in a 128-bit service
  UUID.
- Apple doesn't publish iOS's scan duty cycle or advertising interval. Measure
  the latency; don't assume it.

## 4. Hardware

### 4.1 Chip: Nordic nRF52810-QCAA-R (LCSC C519278)

- QFN-32, 5 × 5 mm, 0.5 mm pitch. Listed "Economic and Standard"; 2,212 in stock
  at $3.62 each on 5 Nov 2026.
- 192 KB flash, 24 KB RAM, BLE 5, DC/DC converter, 17 GPIOs.
- **Why chip-down:** the JLC library has no nRF52 module in stock (all zero,
  checked 5 Nov 2026). The nRF52832-QFAA (C77540) is the fallback: eligible, in
  stock, $5.11, but QFN-48 at 0.4 mm pitch, exactly Economic's limit.
  The nRF52805 is WLCSP only and too fine-pitched for Economic.

### 4.2 Support circuit

Follow **Nordic's nRF52810 QFN-32 reference circuit** (the "reference layout"
package on nordicsemi.com) for the decoupling, the DC/DC components, the 32 MHz
crystal and the RF matching network. Copy the values and topology; don't
improvise.

- **DC/DC:** DCC (pin 31) → 10 µH (C1035, basic) → 15 nH (C27143) → DEC4
  (pin 30). Firmware enables DC/DC; it cuts radio current by roughly a third.
- **HFXO:** 32 MHz, 2016 package (C718072 YXC X201632MKB4SI, or another
  in-stock 2016 part with the same load capacitance), with load caps sized to
  the crystal's CL as Nordic's reference describes.
- **LFCLK:** internal RC oscillator, no 32.768 kHz crystal **[Claude's call]**.
  Good enough for advertise and scan with BLE's 500 ppm allowance, and it saves
  a part and two pins. P0.00/P0.01 stay free for the crystal if it's ever
  wanted.
- **Antenna:** Johanson **2450AT18D0100E** chip antenna (C2917718, $0.72,
  1,644 in stock on 5 Nov 2026), laid out to **Johanson's published reference
  layout** for that part (ground clearance, feed and matching footprint), fed
  from Nordic's π-match. Martin chose this over a printed trace antenna for
  the first run: there's no VNA to tune a trace antenna, and the chip
  antenna's reference layout makes a first spin far more likely to work.
  Keep 0402 footprints for every matching position, so the match can be
  retuned by hand without a respin. No copper on either layer within the
  antenna's keep-out area, which is in Johanson's layout. Keep the metal cell
  holder as far from the antenna as the board allows.
- **Antenna placement:** at the end away from the button, so the thumb and
  hand don't cover it.

### 4.3 Power

- CR2032 SMD holder, keyed, so the cell can't go in backwards. Candidates:
  MYOUNG MY-2032-12 (C964833) or Q&J CR2032-BS-6-1 (C70377). The builder picks
  one that is in stock, SMD, and listed "Economic and Standard", and confirms
  its footprint from the datasheet.
- 22 µF MLCC (0805 or 1206, basic part if available) across the cell, close
  to the holder, to supply the radio's short TX/RX start-up peaks
  **[Claude's call]**. Not larger: a big MLCC loses most of its capacitance
  under DC bias, and its worst-case datasheet leakage could rival the ~2 µA
  sleep budget. No capacitor can carry the 2 s scan; §7 limits that load
  instead.
- No regulator: the nRF52810 runs directly from 1.7–3.6 V.
- No reverse-polarity part, because the holder is keyed **[Claude's call]**.
- No power switch: sleep current is the off state.

### 4.4 User interface

- **Button:** SMD tactile switch, 5.1 × 5.1 mm (C318884 XKB TS-1187A-B-A-B,
  basic), between its GPIO and GND, with an **external 1 MΩ pull-up** to VDD
  (0402); the internal pull-up stays off **[Claude's call]**. A button held
  down in a pocket would otherwise draw ~230 µA through the ~13 kΩ internal
  pull-up and empty the cell in weeks; with 1 MΩ it draws 3 µA.
  Through-board height and actuator style are Martin's call for the case;
  pick another TS-1187A variant if he wants a taller actuator.
- **LED:** **red** 0603 (C2286 KT-0603R, basic) with a 0402 series resistor,
  driven high-active from a GPIO. Red because its ~2.0 V forward voltage still
  works on a run-down coin cell (~2.4 V). Green and blue LEDs (~2.8–3.2 V)
  would be dim or dark at that voltage. Resistor ~470 Ω for ~2 mA at 3.0 V
  **[Claude's call]**; adjust for brightness on the first boards.

### 4.5 Fob ID jumpers

- Three normally-open solder jumpers (two half-pads each), each from a GPIO to
  GND. Closed = 1. ID = bit2·4 + bit1·2 + bit0, so 0–7. All open = ID 0.
- Firmware enables the pull-ups **only for the instant it reads them**, then
  disconnects the pins (input buffer off, no pull). A closed jumper with the
  pull-up left on draws ~230 µA, which would empty the cell in weeks.
- Label each jumper on the silkscreen with its bit value (1, 2, 4).

### 4.6 Debug and programming

- **Tag-Connect TC2030 footprint, the legged ("clip") version:** six pads plus
  three non-plated holes for the cable's retaining legs. Martin will buy the
  TC2030-CTX cable (10-pin Cortex debug end). Keep the bottom side under the
  legs clear (it is: single-sided board).
- TC2030 pinout (ARM 10-pin mapping): 1 VTref/VDD, 2 SWDIO, 3 nRESET (P0.21),
  4 SWDCLK, 5 GND, 6 SWO (P0.18).
- The fob is powered by its own cell while programming; the probe only senses
  VTref.

### 4.7 Breakout header

- An **unpopulated** 2×6 1.27 mm-pitch through-hole header footprint: 10 spare
  GPIOs plus VDD and GND. JLC places nothing, so it costs nothing. Martin
  solders on a header or IDC ribbon connector when a board needs it.
- Silkscreen pin 1 and every pin name (on the top side, beside the footprint).

### 4.8 Pin assignment

From Nordic's nRF52810 QFN-32 pin table (docs.nordicsemi.com, ps_nrf52810).
Nordic's DevZone reports that an older pin *figure* had P0.16 in the wrong
place. Check against the current revision's **table**.

| Pin | Signal | Use |
|---|---|---|
| 2 | P0.00 / XL1 | Breakout (LFXO if ever fitted) |
| 3 | P0.01 / XL2 | Breakout (LFXO if ever fitted) |
| 4 | P0.04 / AIN2 | Breakout |
| 5 | P0.05 / AIN3 | Breakout |
| 6 | P0.06 | **Button** |
| 7 | P0.09 | **LED** |
| 8 | P0.10 | Breakout |
| 10 | P0.12 | **ID bit 0** |
| 11 | P0.14 | **ID bit 1** |
| 12 | P0.15 | **ID bit 2** |
| 13 | P0.16 | Breakout |
| 14 | P0.18 | TC2030 SWO |
| 15 | P0.20 | Breakout |
| 16 | P0.21 / nRESET | TC2030 nRESET |
| 26 | P0.25 | Breakout (Nordic: low-drive, low-frequency use only, as it's near the radio) |
| 27 | P0.28 / AIN4 | Breakout |
| 28 | P0.30 / AIN6 | Breakout |
| 17, 18 | SWDCLK, SWDIO | TC2030 |
| 19 | ANT | Matching network → antenna |

17 GPIOs − 5 (button, LED, 3 jumpers) − 2 (SWO, reset) = **10 spare**, which
exactly fills the 2×6 header's 10 signal pins. SWO is optional: P0.18 could
move to the header if trace output is never wanted. **[Claude's call; the
builder may move pins for routing**, provided the button and ID jumpers stay on
plain GPIOs and P0.25 isn't used for the LED.]

Battery voltage is measured on the chip's internal VDD channel; no pin needed.

## 5. Board

- 2 layers, 1.6 mm, standard stackup, every part on the top side. The bottom is
  bare copper/ground pour (and the TC2030 leg holes).
- **Target size:** about 25 × 45 mm, no more than ~28 × 50 mm, with rounded
  corners. Rough layout: antenna and keep-out area at one end, nRF52810 and
  passives in the middle, button and LED, CR2032 holder at the other end.
  Martin may change the shape once he starts on the case.
- Solid ground pour on both layers outside the antenna keep-out area, stitched
  with vias, especially round the RF path and the chip's ground pad.
- 50 Ω (or as short as possible) feed from ANT through the π-match to the
  antenna, per Nordic's reference layout.
- A mounting hole or keyring slot is up to Martin's case design; leave room
  for one at the battery end **[Claude's call]**.
- Surface finish: HASL on green is the cheapest Economic option. ENIG (green,
  1.6 mm) is flatter, which helps a 0.5 mm QFN; choose it if the quote
  difference is small **[Claude's call; check the price in IREM-5]**.
- **Exports for the case:** board outline DXF, and STEP of the assembled board,
  with button, LED and cell positions.

## 6. Over-the-air protocol (draft; IREM-2 finalises it for the app)

### 6.1 Press advert (fob → phone)

Legacy, non-connectable, undirected advertising (`ADV_NONCONN_IND`). Random
static address.

| AD structure | Bytes | Contents |
|---|---|---|
| Complete list of 128-bit service UUIDs | 18 | The **iphone-remote press UUID** (fixed, generated once, in the firmware and the app) |
| Manufacturer specific data | 9 | Company ID `0xFFFF` (reserved for testing/internal use) + payload below |

Payload (after the company ID), 5 bytes:

| Field | Bytes | Meaning |
|---|---|---|
| version | 1 | Protocol version, `0x01` |
| fob_id | 1 | 0–7, from the jumpers |
| counter | 2 | Press counter, little-endian, wraps at 65535 |
| battery | 1 | VDD in units of 20 mV (e.g. 150 = 3.00 V) |

27 bytes total, inside the 31-byte limit. No flags AD: it isn't needed for
non-connectable adverts, and it saves 3 bytes.

The app scans for the press UUID (`scanForPeripherals(withServices:)` with
duplicates allowed) and reads the manufacturer data.

### 6.2 Ack (phone → fob)

The app advertises one or more 128-bit service UUIDs, each an ack:

```
bytes 0–12   fixed ack prefix (13 bytes, generated once)
byte  13     fob_id
bytes 14–15  counter being acknowledged (little-endian)
```

- The app advertises **no local name** and **exactly one** ack UUID at a time.
  iOS adds a 3-byte flags field, so flags + one 128-bit UUID (21 bytes) fits
  the primary advert packet and the fob can use a **passive** scan. A second
  UUID wouldn't fit: iOS would move it to the scan response or its hashed
  overflow area, which a passive scanner never sees. Still to verify on a
  real iPhone (§9).
- If several fobs press at once, the app **queues** acks and advertises each
  for ~150 ms in turn **[Claude's call]**. Each fob listens for 2 s, so up to
  about a dozen queued acks still land in time.
- An ack is advertised for ~150 ms (or until the next queued ack replaces it),
  then advertising stops.
- The app sends the ack the moment it sees a new press, **before** starting the
  capture, so ack latency doesn't depend on the camera.

### 6.3 De-duplication

- The fob sends each press about 15 times; the app acts on a press only when
  `(fob_id, counter)` differs from the last one it saw for that `fob_id`.
- On power-up the fob seeds `counter` from the chip's hardware RNG, so a fob
  that has just had its cell changed doesn't repeat the counter the app last
  saw.
- Two fobs with the same ID are a user error. They'd mostly still work, but
  acks would be ambiguous.

### 6.4 Timing

| Phase | Value |
|---|---|
| Advertising interval during a press | 20 ms |
| Advertising burst | up to 300 ms, or until the ack arrives |
| Scanning | starts with the burst; window 30 ms every 60 ms (50% duty), until the ack arrives or 2 s |
| A second press during the 2 s | starts a new press with the next counter |

**Note for the builder:** Bluetooth 4.x set a 100 ms minimum for
non-connectable adverts; Bluetooth 5.0 lowered it to 20 ms. Confirm the
SoftDevice Controller accepts 20 ms for `ADV_NONCONN_IND`. If it doesn't, use
connectable undirected adverts at 20 ms and reject any connection attempt.

## 7. Firmware behaviour (IREM-6; summary only)

- nRF Connect SDK (Zephyr) with the SoftDevice Controller, roles: broadcaster +
  observer. No GATT, no connections.
- Idle in **System ON** with the button GPIO wake (`SENSE`), LFCLK on the
  internal RC. Target sleep current ≤ 3 µA measured. System OFF would be lower
  (~0.4 µA) but adds a cold-boot delay to every press; System ON was chosen for
  latency.
- On press: debounce by acting on the **first** edge and ignoring further edges
  for ~50 ms; read the jumpers (pull-ups on, read, pull-ups off); increment the
  counter; read VDD; start advertising and scanning together.
- Scan at 50% duty (30 ms window / 60 ms interval) **[Claude's call]**. The
  ack is re-advertised many times in its ~150 ms slot, so half-duty scanning
  still catches it, and it halves the sustained ~5 mA draw that a worn or cold
  CR2032 struggles with.
- If VDD read before the press is below ~2.2 V, skip the LED flash and shorten
  the scan to 1 s, so a tired cell still sends presses **[Claude's call]**.
- On a matching ack: stop advertising and scanning, flash the LED once (~50 ms).
- On 2 s timeout: stop, give two very short flashes ("phone didn't hear")
  **[Claude's call]**, sleep.

## 8. Power budget

Datasheet-level estimates; to be confirmed by measurement.

```
Sleep, System ON + RC LFCLK:   ~2 µA × 8,760 h   ≈ 17.5 mAh/yr
Press, acked in ~150 ms:        ~6 mA × 0.15 s   ≈ 0.25 µAh
Press, no ack (2 s timeout):    ~3 mA avg × 2 s  ≈ 1.7 µAh   (50% scan duty)
LED flash:                      ~2 mA × 50 ms    ≈ 0.03 µAh
```

- 20 presses a day, acked: about 1.8 mAh/yr; sleep dominates, so **about
  10 years**, at which point self-discharge decides anyway.
- 100 presses a day, never acked: ~60 mAh/yr, about 3 years. This is the
  worst case, if the phone's app is never in the foreground.

## 9. Before ordering: checks that guard the order

**No iPhone spike before ordering (Martin's decision).** The iOS side (the
ack UUID in the primary advert packet, passive-scan visibility, end-to-end
latency) is first proved on a real fob after the boards arrive. The board is
largely protocol-agnostic, so a surprise there should be a firmware change,
not a respin.

1. **Firmware size:** build an NCS broadcaster + observer sample for
   `nrf52810` and confirm it fits in 192 KB flash / 24 KB RAM with margin.
   If not, the fallback is the nRF52832 (different footprint, decide before
   layout).
2. **BOM recheck:** every line in stock at the quantity and listed "Economic and
   Standard" on the day of ordering.
3. **ERC and DRC clean**, with JLC's design rules loaded in KiCad.
4. **Antenna keep-out** checked on both copper layers.

**Bring-up firmware:** the post-arrival checks need a minimal advertise-and-sleep
image. It is the first slice of IREM-6 and is in scope for bring-up even while
the rest of IREM-6 is on hold. **Done** for this phase means the IREM-5 quote;
Martin decides whether to order, and how many.

After the boards arrive: an RSSI check with nRF Connect for Mobile at 2 m, and
a sleep-current measurement (µA range; a multimeter on the cell lead or a
current-sense setup on the scope).

## 10. Cost estimate (5 boards)

Part prices from the JLC parts library on 5 Nov 2026; the setup fee from JLC's
capabilities page. **The extended-part fee, stencil, PCB and shipping are
unverified estimates.**

| Item | Estimate |
|---|---|
| PCB, 2-layer, ~25 × 45 mm, 5 pcs | ~$2–4 |
| Economic setup fee | $8.18 |
| Stencil | ~$1.50 |
| Extended-part fees: ~7 parts (nRF52810, crystal, chip antenna, 15 nH, 1–2 RF match parts, cell holder) × ~$3 | ~$21 |
| Chip antenna: $0.72 × 5 | ~$4 |
| 1 MΩ pull-up, 22 µF bulk capacitor | likely basic parts; pennies |
| Parts: ~$4.20 a board × 5 | ~$21 |
| Shipping to the UK + VAT | ~$15–20 |
| **Total** | **~$70–80, about £11–12 a fob** |

10 boards: about £7 a fob, because the fixed fees are shared. IREM-5 replaces
this with a real quote.

## 11. Left to the builder

- Exact footprints, routing and placement inside §5's constraints.
- Choice between equivalent in-stock parts (crystal, holder, passives),
  preferring basic parts.
- The precise π-match values, from Nordic's reference.
- Which spare GPIO is left off the breakout, and the order of breakout pins.
- Generating the two fixed UUIDs (press UUID, ack prefix) and recording them in
  the protocol spec.

## 12. Plane items

| Ref | Item |
|---|---|
| IREM-1 | This design |
| IREM-2 | Protocol spec for the iPhone side (from §6) |
| IREM-3 | Schematic |
| IREM-4 | PCB layout and case exports |
| IREM-5 | BOM, placement file, JLC quote |
| IREM-6 | Firmware (on hold; the §9 size check happens before layout) |
