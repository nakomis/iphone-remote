<img src="docs/logo.png" alt="iphone-remote logo" width="200" align="right"/>

# iphone-remote — A coin-cell BLE trigger fob for a custom iPhone camera app

## Support

If you find this useful, please consider buying me a coffee:

[![Donate with PayPal](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate?hosted_button_id=Q3BESC73EWVNN&custom=iphone-remote)

## Table of Contents

<!-- toc -->

- [What it is](#what-it-is)
- [Architecture Diagram](#architecture-diagram)
- [Repository Layout](#repository-layout)
- [Architecture Diagrams](#architecture-diagrams)
- [Support](#support)

<!-- tocstop -->

## What it is

A car-key-sized fob with one button. Press it and a custom iPhone camera app,
about six feet away, takes a photo. An LED on the fob flashes when the phone
acknowledges the press.

- **Radio:** advertising-only Bluetooth Low Energy. No pairing, no connection.
  The fob wakes on a press, broadcasts a short burst of adverts, listens briefly
  for an acknowledgement advert from the phone, and goes back to sleep.
- **Power:** a CR2032 coin cell, for years.
- **Chip:** Nordic nRF52810 (QFN-32), on a 2-layer board assembled by JLCPCB
  using their Economic (single-sided) service.
- **Several fobs, one phone:** three solder jumpers set a fob ID from 0 to 7.

The full design is in [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Architecture Diagram

![Architecture](docs/architecture/iphone-remote.svg)

## Repository Layout

| Path | Contents |
|---|---|
| `hardware/` | KiCad project: schematic, PCB, BOM and placement files for JLCPCB |
| `firmware/` | nRF Connect SDK (Zephyr) firmware for the nRF52810 |
| `docs/superpowers/specs/` | Design document and over-the-air protocol |
| `docs/architecture/` | Architecture diagram source (draw.io) |
| `docs/logo-candidates/` | Logo candidates awaiting a verdict |

## Architecture Diagrams

`docs/architecture/iphone-remote.drawio` is the source for the diagram above.
The SVG is auto-regenerated on commit by the pre-commit hook in `.githooks/pre-commit`.

To activate the hook after cloning:

```bash
git config core.hooksPath .githooks
```

## Support

If you find this useful, please consider buying me a coffee:

[![Donate with PayPal](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate?hosted_button_id=Q3BESC73EWVNN&custom=iphone-remote)
