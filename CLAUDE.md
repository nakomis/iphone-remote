# iphone-remote

A coin-cell BLE trigger fob for a custom iPhone camera app. Plane project: `IREM`.

## Key decisions

- **Advertising-only BLE.** No pairing, no connection, no GATT server. The fob
  advertises a press (fixed service UUID + fob ID + rolling counter), then scans
  up to 2 s for the phone's ack advert, then sleeps. The phone can only
  advertise local name + service UUIDs, so the ack is encoded inside a 128-bit
  service UUID.
- **nRF52810-QCAA (QFN-32, LCSC C519278), chip-down.** No nRF52 module was in
  stock at JLCPCB (Nov 2026). QFN-32 at 0.5 mm pitch is inside JLC Economic's
  0.4 mm minimum; the WLCSP nRF52805 is not.
- **JLCPCB Economic PCBA is a hard constraint.** Single-sided placement, 0402
  minimum, 2 layers, 0.8–1.6 mm thick, no castellations or gold fingers. Every
  BOM line must be in stock and listed as "Economic and Standard". Check
  extended-part count: each costs a feeder fee.
- **CR2032.** Sleep current matters more than anything else. Jumper pull-ups
  are enabled only for the instant they are read.
- Martin designs the case; the board outline is exported for him.

## Repository layout

- `hardware/` — KiCad project
- `firmware/` — nRF Connect SDK (Zephyr) application
- `docs/superpowers/specs/` — design document
- `docs/protocol.md` — the over-the-air protocol (IREM-2): UUIDs, payload, ack, test vectors

## Testing

Firmware logic that doesn't touch hardware (payload encoding, counter and ack
matching) gets host-side unit tests (Zephyr ztest on `native_sim`), 70% minimum.
Hardware: KiCad ERC and DRC must be clean before ordering.

## Architecture diagrams

Source: `docs/architecture/iphone-remote.drawio` — SVG auto-regenerated on commit by `.githooks/pre-commit`.

To activate the hook after cloning:
```bash
git config core.hooksPath .githooks
```
