"""iphone-remote fob (IREM-3): nRF52810-QCAA on a CR2032, one button, a red ack LED, three
fob-ID solder jumpers, an unpopulated 2x6 1.27 mm breakout and a Tag-Connect TC2030 SWD footprint.

The circuit follows Nordic's nRF52810 "QCAA QFN32 with DC/DC regulator setup" reference
(docs.nordicsemi.com, ps_nrf52810, Reference circuitry, read 5 Nov 2026); reference designators
in comments (C1..C10, L1..L3, X1) are Nordic's, so the two can be compared line by line. Design
document: docs/superpowers/specs/2026-11-05-iphone-remote-fob-design.md.
"""
from board.netlist import Circuit

GND, VBAT = "GND", "VBAT"

# GPIO assignment (design doc section 4.8). Net names use P0_nn.
BUTTON, LED = "P0.06", "P0.09"
ID_BITS = ("P0.12", "P0.14", "P0.15")          # bit 0, 1, 2
SWO, NRESET = "P0.18", "P0.21/nRESET"
# Breakout header J2: pin 1 VBAT, pin 2 GND, then the ten spare GPIOs on pins 3..12.
BREAKOUT = ("P0.00/XL1", "P0.01/XL2", "P0.04/AIN2", "P0.05/AIN3", "P0.10", "P0.16", "P0.20",
            "P0.25", "P0.28/AIN4", "P0.30/AIN6")
# TC2030 pin -> net (Tag-Connect TC2030-CTX, ARM Cortex 10-pin mapping).
TC2030_PINS = {"1": VBAT, "2": "SWDIO", "3": "NRESET", "4": "SWDCLK", "5": GND, "6": "SWO"}


def net(pin):
    """Net name for a chip pin name: 'P0.30/AIN6' -> 'P0_30'."""
    return pin.split("/")[0].replace(".", "_")


def _cap(c, key, ref, a, b=GND, dnp=False):
    cap = c.add(key, ref, dnp=dnp)
    c.connect(a, (cap, "1"))
    c.connect(b, (cap, "2"))
    return cap


def build_fob():
    c = Circuit()
    u1 = c.add("NRF", "U1")

    # Power: CR2032 straight onto VDD (1.7-3.6 V, no regulator). The holder's two side clips
    # (pad 1) touch the cell's + can; the centre pad (2) is the cell's - face.
    bt = c.add("BAT", "BT1")
    c.connect(VBAT, (bt, "1"))
    c.connect(GND, (bt, "2"))
    _cap(c, "C22U", "C11", VBAT)                       # bulk, beside the holder (doc 4.3)

    c.connect(VBAT, (u1, "VDD"))
    c.connect(GND, (u1, "VSS"), (u1, "EP"))
    _cap(c, "C4U7", "C9", VBAT)                        # Nordic C9 at VDD pin 32
    _cap(c, "C100N", "C5", VBAT)                       # Nordic C5 at VDD pin 9
    _cap(c, "C100N", "C8", VBAT)                       # Nordic C8 at VDD pin 25
    c.connect("DEC1", (u1, "DEC1"))
    _cap(c, "C100N", "C4", "DEC1")                     # Nordic C4
    c.connect("DEC3", (u1, "DEC3"))
    _cap(c, "C100P", "C7", "DEC3")                     # Nordic C7
    c.no_connect(u1, "DEC2")                           # Nordic C6 is "N.C."

    # DC/DC: DCC -> 10 uH (L2) -> 15 nH (L3) -> DEC4, 1 uF (C10) on DEC4.
    c.connect("DCC", (u1, "DCC"), (c.add("L10U", "L2"), "1"))
    c.connect("DCDC_L", (c.instances["L2"], "2"), (c.add("L15N", "L3"), "1"))
    c.connect("DEC4", (c.instances["L3"], "2"), (u1, "DEC4"))
    _cap(c, "C1U", "C10", "DEC4")

    # 32 MHz crystal (X1, CL 8 pF) with 12 pF load capacitors (C1, C2).
    y1 = c.add("XTAL", "Y1")
    c.connect("XC1", (u1, "XC1"), (y1, "1"))
    c.connect("XC2", (u1, "XC2"), (y1, "3"))
    c.connect(GND, (y1, "GND"))
    _cap(c, "C12P", "C1", "XC1")
    _cap(c, "C12P", "C2", "XC2")

    # RF: Nordic's match, 0.8 pF shunt at ANT (C3) then 3.9 nH series (L1), giving a 50 ohm feed
    # (RF). Then a pi footprint for tuning the chip antenna by hand: shunt (CA1, not fitted),
    # 0 R series (R3), shunt (CA2, not fitted), as Johanson's reference layout allows for.
    c.connect("ANT", (u1, "ANT"))
    _cap(c, "C0P8", "C3", "ANT")
    c.connect("ANT", (c.add("L3N9", "L1"), "1"))
    c.connect("RF", (c.instances["L1"], "2"))
    _cap(c, "CDNP", "CA1", "RF", dnp=True)
    c.connect("RF", (c.add("R0", "R3"), "1"))
    c.connect("ANT_FEED", (c.instances["R3"], "2"))
    _cap(c, "CDNP", "CA2", "ANT_FEED", dnp=True)
    ae = c.add("ANT", "AE1")
    c.connect("ANT_FEED", (ae, "Feed"))
    c.connect(GND, (ae, "GND"))

    # Button to GND with an external 1 M pull-up (internal pull-up off; doc 4.4). The switch's
    # diagonal pads B and C are on different contact bars whichever way the pairs go.
    sw = c.add("SW", "SW1")
    c.connect(net(BUTTON), (u1, BUTTON), (sw, "B"), (c.add("R1M", "R2"), "1"))
    c.connect(VBAT, (c.instances["R2"], "2"))
    c.connect(GND, (sw, "C"))

    # Red LED, high-active through 470 R.
    d1 = c.add("LED", "D1")
    c.connect(net(LED), (u1, LED), (c.add("R470", "R1"), "1"))
    c.connect("LED_A", (c.instances["R1"], "2"), (d1, "A"))
    c.connect(GND, (d1, "K"))

    # Fob ID: three normally-open solder jumpers to GND (closed = 1).
    for bit, pin in enumerate(ID_BITS):
        jp = c.add("JUMPER", f"JP{bit + 1}")
        c.connect(net(pin), (u1, pin), (jp, "1"))
        c.connect(GND, (jp, "2"))

    # SWD: Tag-Connect TC2030 (legged), SWO on P0.18 and nRESET on P0.21.
    j1 = c.add("TC2030", "J1")
    c.connect("SWDIO", (u1, "SWDIO"))
    c.connect("SWDCLK", (u1, "SWDCLK"))
    c.connect("SWO", (u1, SWO))
    c.connect("NRESET", (u1, NRESET))
    for pad, n in TC2030_PINS.items():
        c.connect(n, (j1, pad))

    # Breakout J2 (not fitted by JLC; Martin solders a header when he needs it).
    j2 = c.add("HDR", "J2")
    c.connect(VBAT, (j2, "1"))
    c.connect(GND, (j2, "2"))
    for i, pin in enumerate(BREAKOUT):
        c.connect(net(pin), (u1, pin), (j2, str(i + 3)))
    return c


def pins_h():
    """The firmware header: nRF52810 pin numbers as wired on this board."""
    num = lambda pin: int(pin.split("/")[0].split(".")[1])
    lines = ["/* Generated by hardware/fob/build.py from board/fob_board.py: do not edit. */",
             "#pragma once", "",
             f"#define FOB_PIN_BUTTON {num(BUTTON)}   /* active low, external 1M pull-up */",
             f"#define FOB_PIN_LED {num(LED)}      /* active high, red, 470R */"]
    for bit, pin in enumerate(ID_BITS):
        lines.append(f"#define FOB_PIN_ID_BIT{bit} {num(pin)}  /* jumper to GND, closed = 1 */")
    lines.append("")
    lines.append("/* Breakout J2: pin 1 VBAT, pin 2 GND, then: */")
    for i, pin in enumerate(BREAKOUT):
        lines.append(f"/*   J2.{i + 3}: P0.{num(pin):02d} */")
    return "\n".join(lines) + "\n"
