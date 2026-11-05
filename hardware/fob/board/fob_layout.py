"""Fob layout (IREM-4): placement, keep-outs and the hand-routed RF chain.

Board frame (KiCad, y down): x 0..W, y 0..L. The chip antenna sits on the y = 0 edge (Johanson's
edge-mount layout), the nRF52810 just below it, then the ID jumpers, the button and LED, and the
CR2032 holder at the far end, so the hand and the cell are as far from the antenna as the board
allows. Every part is on the top side (JLC Economic).
"""
import math

from board.kicad_pcb import Track, Via
from board.placement import Placement, rotate

W, L = 29.0, 47.0

# nRF52810 centre; its top pad row (17..24) faces the antenna, ANT (pin 19) at x + 0.75.
UX, UY = 11.5, 6.6
# Antenna: pad 1 (feed) at (AX - 1.5, AY + 0.65), pads 2-4 GND. The RF line runs at y = RF_Y.
AX, AY = 23.2, 1.3
RF_Y = round(AY + 0.65, 3)                     # 1.95
# CR2032 holder centre; the cell (20 mm) sits on the centre pad, the clips at x +- 11.35.
BX, BY = W / 2, round(L - 12.4, 2)

# Pin geometry of U1 (QFN-32, 0.5 mm pitch, pads 0.25 x 0.9 centred 2.65 from the centre):
# top row 24..17 left to right at y 3.95, left column 25..32 top to bottom at x 8.85,
# bottom row 1..8 at y 9.25, right column 16..9 top to bottom at x 14.15.
AT = {
    "U1": (UX, UY, 0),
    # RF along the top edge: the ANT pin rises to the line at C3 (0.8 pF shunt, Nordic's match),
    # then L1 (3.9 nH) in series, then the tuning pi CA1 / R3 / CA2 (shunts above the line, not
    # fitted) and the antenna's feed pad.
    "C3": (11.83, RF_Y, 180), "L1": (13.75, RF_Y, 0),
    "CA1": (16.3, round(RF_Y - 0.92, 3), 90), "R3": (17.85, RF_Y, 0),
    "CA2": (19.35, round(RF_Y - 0.92, 3), 90), "AE1": (AX, AY, 0),
    # DEC3 (pin 22) cap straight above its pin, GND end above VSS (pin 20)
    "C7": (11.17, 3.0, 0),
    # crystal, its load caps, and VDD pin 25's cap, top left
    "Y1": (7.6, 2.3, 270), "C1": (5.45, 1.6, 180), "C2": (9.35, 2.25, 90),
    "C8": (7.3, 4.8, 180),
    # DC/DC and VDD pin 32, bottom left: DEC4 lane (pin 30) to C10 and L3, DCC lane (pin 31) to L2
    "C10": (4.8, 6.35, 90), "L2": (6.3, 8.75, 270), "L3": (4.8, 8.9, 90), "C9": (7.7, 9.3, 270),
    # DEC1 (pin 1) below; VDD pin 9 to the right
    "C4": (9.75, 10.55, 270), "C5": (14.6, 10.25, 270),
    # SWD on the right; the breakout under the chip, its pins in a row along x
    "J1": (24.0, 11.6, 0), "J2": (6.8, 15.0, 90),
    # fob-ID jumpers (bits 0, 1, 2 left to right), labelled 1 / 2 / 4
    "JP1": (17.6, 18.4, 0), "JP2": (21.1, 18.4, 0), "JP3": (24.6, 18.4, 0),
    # button, its pull-up, the LED and its resistor
    "SW1": (6.0, 21.8, 0), "R2": (3.2, 18.4, 90), "D1": (12.5, 21.6, 0), "R1": (12.5, 23.3, 0),
    # bulk capacitor just above the cell, by the + clip on the right
    "C11": (23.5, 22.6, 0),
    "BT1": (BX, BY, 0),
}

# The holder's footprint courtyard covers only its pads; the holder and cell are a ~24 mm disc.
BODY = {"BT1": (-12.8, -12.2, 12.8, 12.2)}


def place_fob(circuit):
    at = {r: AT[r] for r in circuit.instances}
    bodies = {r: BODY.get(r, i.part.body) for r, i in circuit.instances.items()}
    return Placement((0.0, 0.0, W, L), at, bodies)


def pad_xy(circuit, ref, number):
    """Exact board position of a pad centre."""
    x, y, rot = AT[ref]
    q = next(q for q in circuit.instances[ref].part.footprint.pads if q.number == number)
    dx, dy = rotate(q.x, q.y, rot)
    return round(x + dx, 4), round(y + dy, 4)


# Antenna ground clearance (Johanson evaluation board): 4.0 x 6.0 mm from the board edge, no
# copper on any layer, the antenna's own pads excepted. F.Cu: the strip between the pad pairs,
# then the full width below the pads; B.Cu: the whole box.
ANT_BOX = (AX - 2.0, 0.0, AX + 2.0, 6.0)

# Kappa on the back, under the cell holder (house rule: a cat portrait and the credit on every
# board). White mask, black silk: the silk is his dark fur. art/make_kappa.py makes the PNG.
HERE = __import__("pathlib").Path(__file__).resolve().parent.parent
ART_PNG = HERE / "art" / "kappa.png"
ART_PX = 0.15                        # mm per pixel: 130 x 159 px -> 19.5 x 23.85 mm
ART_W, ART_H = 19.5, 23.85
ART_X, ART_TOP = round(W / 2 - ART_W / 2, 3), 20.6
ART_BOX = (ART_X - 0.4, ART_TOP - 0.4, ART_X + ART_W + 0.4, ART_TOP + ART_H + 0.4)
CREDIT = "Designed by Nakomis/C"
CREDIT_Y = round(ART_TOP + ART_H + 1.0, 2)
CREDIT_BOX = (W / 2 - 8.0, CREDIT_Y - 1.0, W / 2 + 8.0, CREDIT_Y + 1.0)
_PAD_BOTTOM = round(AY + 0.65 + 0.3 + 0.1, 3)


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def keepouts():
    x0, y0, x1, y1 = ANT_BOX
    return [("ANTENNA_GAP", _rect(AX - 1.0, 0.0, AX + 1.0, _PAD_BOTTOM), ["F.Cu"]),
            ("ANTENNA_CLEAR", _rect(x0, _PAD_BOTTOM, x1, y1), ["F.Cu"]),
            ("ANTENNA_CLEAR_B", _rect(x0, y0, x1, y1), ["B.Cu"])]


def route_area():
    return [(0.0, 0.0), (W, 0.0), (W, L), (0.0, L)]


def layer_keepouts():
    """Router-only areas: nothing but the GND pour on F.Cu under the cell (its - face lies on
    the board), and no routing at all in the antenna's clearance."""
    cell = ("F.Cu", BX - 10.5, BY - 10.5, BX + 10.5, BY + 10.5)
    x0, y0, x1, y1 = ANT_BOX
    # Keep B.Cu solid GND under the chip body and under the RF line: the router may not run
    # tracks there (the pour fills it, with the exposed pad's vias).
    under_chip = ("B.Cu", UX - 2.5, UY - 2.2, UX + 2.5, UY + 2.4)
    under_rf = ("B.Cu", 12.0, 0.3, x0, RF_Y + 0.45)
    return [cell, ("F.Cu", x0, y0, x1, y1), ("B.Cu", x0, y0, x1, y1), under_chip, under_rf] + npth_keepouts()


def npth_keepouts(c=None, margin=0.0):
    """The router doesn't see the TC2030's leg holes (non-plated, no pad number), so each gets a
    round keep-out on both layers: hole + the 0.25 mm hole clearance + a margin, each side."""
    from board.parts import PARTS
    jx, jy, rot = AT["J1"]
    out = []
    for q in PARTS["TC2030"].footprint.pads:
        if q.kind != "np_thru_hole":
            continue
        dx, dy = rotate(q.x, q.y, rot)
        d = round(max(q.w, q.h) + 2 * (0.25 + margin), 3)
        for layer in ("F.Cu", "B.Cu"):
            out.append(("circle", layer, d, round(jx + dx, 3), round(jy + dy, 3)))
    return out


RF_W = 0.5            # short (< 6 mm) RF runs between 0402 pads; ground pour either side
PIN_W = 0.25          # ANT pin escape: the QFN pad width, so it clears pins 18 and 20


def _segments(net, layer, pts, width):
    return [Track(net, layer, a, b, c, d, width) for (a, b), (c, d) in zip(pts, pts[1:]) if (a, b) != (c, d)]


def rf_hand_route(c):
    """(tracks, vias) for everything hand-routed round U1 (all F.Cu unless noted): the RF chain,
    the crystal, DEC1/3/4, the DC/DC, VDD to its three caps, the escapes the router can't find
    (P0.25/28/30 and SWD to vias), and short GND ties to vias where the pour can't reach."""
    P = lambda ref, n: pad_xy(c, ref, n)
    t, v = [], []
    # RF: riser at the pin's own width, then RF_W
    p19, c3, l1a, l1b = P("U1", "19"), P("C3", "1"), P("L1", "1"), P("L1", "2")
    r3a, r3b, ca1, ca2, feed = P("R3", "1"), P("R3", "2"), P("CA1", "1"), P("CA2", "1"), P("AE1", "1")
    t += _segments("ANT", "F.Cu", [p19, (p19[0], c3[1])], PIN_W)
    t += _segments("ANT", "F.Cu", [c3, l1a], RF_W)
    t += _segments("RF", "F.Cu", [l1b, (ca1[0], RF_Y), r3a], RF_W) + _segments("RF", "F.Cu", [(ca1[0], RF_Y), ca1], RF_W)
    t += _segments("ANT_FEED", "F.Cu", [r3b, (ca2[0], RF_Y), feed], RF_W)
    t += _segments("ANT_FEED", "F.Cu", [(ca2[0], RF_Y), ca2], RF_W)
    w = 0.15
    # DEC3 up to C7; C7's GND end down to VSS pin 20, and across to C3's GND end and a via
    p22, c7a, c7b, p20, c3g = P("U1", "22"), P("C7", "1"), P("C7", "2"), P("U1", "20"), P("C3", "2")
    t += _segments("DEC3", "F.Cu", [p22, c7a], 0.2)
    gv = Via("GND", 10.95, 1.35)
    t += _segments("GND", "F.Cu", [c7b, p20], 0.2) + _segments("GND", "F.Cu", [c7b, c3g, (gv.x, gv.y)], 0.25)
    v.append(gv)
    # crystal: XC1 up the outside and over the top to Y1 pad 1 (C1 beside it); XC2 left along
    # y 3.05 under C2 to Y1 pad 3; Y1's GND pads tied under the crystal and to a via
    p23, p24, y1, y3, y2, y4 = P("U1", "23"), P("U1", "24"), P("Y1", "1"), P("Y1", "3"), P("Y1", "2"), P("Y1", "4")
    c1a, c1b, c2a, c2b = P("C1", "1"), P("C1", "2"), P("C2", "1"), P("C2", "2")
    t += _segments("XC1", "F.Cu", [p23, (p23[0], 0.6), (y1[0], 0.6), y1, c1a], w)
    t += _segments("XC2", "F.Cu", [p24, (p24[0], 3.05), (y3[0], 3.05), y3], w)
    t += _segments("XC2", "F.Cu", [(c2a[0], 3.05), c2a], w)
    yv, c1v = Via("GND", 6.2, 3.0), Via("GND", 4.4, 1.6)
    t += _segments("GND", "F.Cu", [c2b, y4, y2, (yv.x, yv.y)], 0.2) + _segments("GND", "F.Cu", [c1b, (c1v.x, c1v.y)], 0.25)
    v += [yv, c1v]
    # VDD pin 25 to C8 (GND end to a via)
    p25, c8a, c8b = P("U1", "25"), P("C8", "1"), P("C8", "2")
    c8v = Via("GND", 6.88, 4.1)
    t += _segments("VBAT", "F.Cu", [p25, c8a], 0.2) + _segments("GND", "F.Cu", [c8b, (c8v.x, c8v.y)], 0.25)
    v.append(c8v)
    # P0.25 / P0.28 / P0.30 escape left to staggered vias (the router carries them on from there)
    for pin, net, (vx, vy) in (("26", "P0_25", (5.75, 5.35)), ("27", "P0_28", (6.75, 6.05)), ("28", "P0_30", (7.75, 6.5))):
        pp = P("U1", pin)
        t += _segments(net, "F.Cu", [pp, (round(pp[0] - 0.6, 3), pp[1]), (vx, vy)], w)
        v.append(Via(net, vx, vy))
    # DEC4 lane (pin 30) to C10 and L3; DCC lane (pin 31) to L2; L2 to L3; VDD pin 32 to C9
    p30, p31, p32 = P("U1", "30"), P("U1", "31"), P("U1", "32")
    c10a, c10b, l2a, l2b, l3a, l3b = P("C10", "1"), P("C10", "2"), P("L2", "1"), P("L2", "2"), P("L3", "1"), P("L3", "2")
    c9a, c9b = P("C9", "1"), P("C9", "2")
    t += _segments("DEC4", "F.Cu", [p30, (c10a[0], p30[1]), c10a], 0.2) + _segments("DEC4", "F.Cu", [(l3b[0], p30[1]), l3b], 0.2)
    t += _segments("DCC", "F.Cu", [p31, (l2a[0], p31[1]), l2a], 0.2)
    t += _segments("DCDC_L", "F.Cu", [l2b, l3a], 0.25)
    t += _segments("VBAT", "F.Cu", [p32, (c9a[0], p32[1]), c9a], 0.2)
    # VBAT vias beside C8, C9 and C5, so the router can carry VBAT on B.Cu out of the crowd
    vb1, vb2, vb3 = Via("VBAT", 8.55, 3.98), Via("VBAT", 8.75, 9.35), Via("VBAT", 15.5, 9.83)
    t += _segments("VBAT", "F.Cu", [c8a, (vb1.x, vb1.y)], 0.2) + _segments("VBAT", "F.Cu", [c9a, (vb2.x, vb2.y)], 0.2)
    v += [vb1, vb2, vb3]
    c10v, c9v = Via("GND", 4.8, 4.75), Via("GND", 7.7, 10.75)
    t += _segments("GND", "F.Cu", [c10b, (c10v.x, c10v.y)], 0.25) + _segments("GND", "F.Cu", [c9b, (c9v.x, c9v.y)], 0.25)
    v += [c10v, c9v]
    # DEC1 (pin 1) down to C4; VDD pin 9 to C5
    p1, c4a, c4b, p9, c5a, c5b = P("U1", "1"), P("C4", "1"), P("C4", "2"), P("U1", "9"), P("C5", "1"), P("C5", "2")
    t += _segments("DEC1", "F.Cu", [p1, c4a], 0.2)
    t += _segments("VBAT", "F.Cu", [p9, (c5a[0], p9[1]), c5a, (15.5, c5a[1])], 0.2)
    c4v, c5v = Via("GND", 9.0, 11.25), Via("GND", 14.6, 11.4)
    # nRESET (pin 16, top of the right column) escapes right to a via
    p16 = P("U1", "16")
    rv = Via("NRESET", 16.1, 4.5)
    t += _segments("NRESET", "F.Cu", [p16, (15.6, p16[1]), (rv.x, rv.y)], w)
    v.append(rv)
    # P0.14 (ID bit 1, pin 11) escapes right to a via; its neighbours route round it
    p11 = P("U1", "11")
    iv = Via("P0_14", 16.35, 7.45)
    t += _segments("P0_14", "F.Cu", [p11, (16.05, p11[1]), (iv.x, iv.y)], w)
    v.append(iv)
    # BUTTON (pin 6) and LED (pin 7) drop to vias between the breakout tracks below the chip
    p6, p7 = P("U1", "6"), P("U1", "7")
    bv, lv = Via("P0_06", 12.25, 10.35), Via("P0_09", 12.6, 12.3)
    t += _segments("P0_06", "F.Cu", [p6, (bv.x, bv.y)], w)
    t += _segments("P0_09", "F.Cu", [p7, (12.85, 9.95), (12.85, 11.6), (lv.x, lv.y)], w)
    v += [bv, lv]
    t += _segments("GND", "F.Cu", [c4b, (c4v.x, c4v.y)], 0.25) + _segments("GND", "F.Cu", [c5b, (c5v.x, c5v.y)], 0.25)
    v += [c4v, c5v]
    # SWD: the top-right pins drop to vias just above the pin row, under the RF line
    p18, p17 = P("U1", "18"), P("U1", "17")
    sv1, sv2 = Via("SWDIO", 12.85, 2.85), Via("SWDCLK", 13.7, 2.85)
    t += _segments("SWDIO", "F.Cu", [p18, (sv1.x, sv1.y)], w) + _segments("SWDCLK", "F.Cu", [p17, (sv2.x, sv2.y)], w)
    v += [sv1, sv2]
    # TC2030 fan-out: one track per gap between the leg holes, each to a via outside them
    # (footprint coordinates; the router joins the vias up). Gaps: two on the left between the
    # alignment hole and the big holes, one above and one below between the big holes, and the
    # gap between the two right-hand alignment holes, which takes two tracks.
    jx, jy, _ = AT["J1"]
    J = lambda pts: [(round(jx + x, 3), round(jy + y, 3)) for x, y in pts]
    fan = (("1", "VBAT", [(-1.9, 0.92), (-4.2, 0.92)]), ("2", "SWDIO", [(-1.9, -0.92), (-4.2, -0.92)]),
           ("3", "NRESET", [(-0.95, 1.59), (-0.95, 4.4)]), ("4", "SWDCLK", [(-0.95, -1.59), (-0.95, -4.4)]),
           ("5", "GND", [(1.9, 0.17), (3.2, 0.17), (3.9, 0.55)]), ("6", "SWO", [(1.9, -0.17), (3.2, -0.17), (3.9, -0.6)]))
    for pad, net, pts in fan:
        path = [P("J1", pad)] + J(pts)
        t += _segments(net, "F.Cu", path, w)
        v.append(Via(net, *path[-1]))
    # ID jumpers: each GND half to a via just below it
    for jp in ("JP1", "JP2", "JP3"):
        g = P(jp, "2")
        jv = Via("GND", g[0], round(g[1] + 1.35, 3))
        t += _segments("GND", "F.Cu", [g, (jv.x, jv.y)], 0.3)
        v.append(jv)
    # GND: pins 20 (by ANT) and 29 (by DEC4) tied straight into the exposed pad
    p29, ep = P("U1", "29"), P("U1", "33")
    t += _segments("GND", "F.Cu", [p20, (p20[0], round(ep[1] - 1.6, 4))], PIN_W)
    t += _segments("GND", "F.Cu", [p29, (round(ep[0] - 1.6, 4), p29[1])], PIN_W)
    return t, v


def ep_vias():
    """Nine GND vias in the nRF52810's exposed pad (3 x 3 at 1.1 mm), into the B.Cu pour."""
    return [Via("GND", round(UX + dx, 3), round(UY + dy, 3)) for dx in (-1.1, 0, 1.1) for dy in (-1.1, 0, 1.1)]


def pad_extra(c):
    """Every GND pad joins the pour solidly rather than through thermal spokes: on a board this
    small the spokes are often starved (one of two), and the parts are small enough to solder."""
    from board.sexpr import Sym
    out = {}
    for ref in c.instances:
        out[ref] = (lambda r: lambda pad: [[Sym("zone_connect"), 2]] if c.net_of(r, pad.number) == "GND" else [])(ref)
    return out


def silk(c):
    """Front silk: the ID jumper weights, button and LED labels, the board name."""
    out = []
    for jp, w in (("JP1", "1"), ("JP2", "2"), ("JP3", "4")):
        x, y, _ = AT[jp]
        out.append((w, x, round(y - 1.9, 3), 0.9))
    out.append(("ID", round(AT["JP1"][0] - 2.6, 3), AT["JP1"][1], 0.9))
    out.append(("SWD", round(AT["J1"][0] - 4.4, 3), round(AT["J1"][1] - 3.6, 3), 0.8))
    out.append(("1", round(AT["J2"][0] - 1.25, 3), round(AT["J2"][1] + 0.9, 3), 0.8))
    out.append(("iphone-remote fob v0.1", W / 2, round(L - 0.9, 3), 0.8))
    out.append((CREDIT, W / 2, CREDIT_Y, 0.8, "B.SilkS"))
    return out


def art():
    """Kappa on B.SilkS, mirrored by the writer so that he reads correctly from the back."""
    return [(ART_PNG, ART_X, ART_TOP, ART_H, "back")]


def edge_vias():
    """GND stitching either side of the RF line and around the antenna clearance."""
    pts = [(13.75, 0.75), (15.05, 0.75), (17.85, 0.75), (15.3, 3.1), (16.9, 3.1), (18.5, 3.1), (20.1, 3.1),
           (26.0, 0.7), (26.0, 2.5), (26.0, 4.3)]
    return [Via("GND", x, y) for x, y in pts]


def _pad_boxes(circuit, placement):
    """(net, xmin, ymin, xmax, ymax) for every copper pad, in board coordinates."""
    out = []
    for ref, inst in circuit.instances.items():
        x, y, rot = placement.at[ref]
        for pad in inst.part.footprint.pads:
            dx, dy = rotate(pad.x, pad.y, rot)
            w, h = (pad.h, pad.w) if round(pad.rot + rot) % 180 == 90 else (pad.w, pad.h)
            out.append((circuit.net_of(ref, pad.number), x + dx - w / 2, y + dy - h / 2,
                        x + dx + w / 2, y + dy + h / 2))
    return out


def _seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = 0.0 if vx == vy == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def stitch_vias(circuit, placement, tracks, vias, pitch=1.0, clear=0.5, avoid=(), avoid_at=None):
    W, L = placement.outline[2], placement.outline[3]
    """GND stitching vias on a grid, wherever a via clears every pad, track and via by 'clear'
    (beyond its own 0.3 mm radius) so that both pours reach it, lies outside the 'avoid'
    boxes (x0, y0, x1, y1), such as silk text, and avoid_at(x, y) is false (Mu's white fur)."""
    pads = _pad_boxes(circuit, placement)
    placed = list(vias)
    out = []
    r = 0.3
    y = 0.8
    while y < L - 0.7:
        x = 0.8
        while x < W - 0.7:
            ok = all(_box_dist(x, y, b) >= r + clear for b in pads)
            ok = ok and not any(x0 - 0.3 <= x <= x1 + 0.3 and y0 - 0.3 <= y <= y1 + 0.3 for x0, y0, x1, y1 in avoid)
            ok = ok and not (avoid_at and avoid_at(x, y))
            ok = ok and all(_seg_dist(x, y, t.x1, t.y1, t.x2, t.y2) >= r + t.width / 2 + clear for t in tracks)
            ok = ok and all(math.hypot(x - v.x, y - v.y) >= 1.3 for v in placed)
            if ok:
                v = Via("GND", round(x, 3), round(y, 3))
                out.append(v)
                placed.append(v)
            x += pitch
        y += pitch
    return out


def _box_dist(x, y, box):
    _, x0, y0, x1, y1 = box
    return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1))


