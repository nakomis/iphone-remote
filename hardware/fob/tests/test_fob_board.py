"""The fob circuit against Nordic's QCAA DC/DC reference and the design document."""
from board.fob_board import BREAKOUT, ID_BITS, TC2030_PINS, build_fob, pins_h
from board.netlist import check
from board.parts import PARTS


def pads(c, net):
    return c.nets[net]


def test_netlist_is_clean():
    assert check(build_fob()) == []


def test_every_fitted_part_is_economic_checked_lcsc_and_board_only_parts_are_not_in_the_bom():
    c = build_fob()
    for ref, inst in c.instances.items():
        if ref[:2] in ("JP", "J1", "J2"):
            assert inst.part.lcsc is None, ref
        elif not inst.dnp:
            assert inst.part.lcsc and inst.part.lcsc.startswith("C"), ref


def test_power_and_decoupling_follow_nordic():
    c = build_fob()
    assert {("U1", "9"), ("U1", "25"), ("U1", "32"), ("BT1", "1")} <= pads(c, "VBAT")
    assert {("U1", "20"), ("U1", "29"), ("U1", "33"), ("BT1", "2")} <= pads(c, "GND")
    assert pads(c, "DEC1") == {("U1", "1"), ("C4", "1")}
    assert pads(c, "DEC3") == {("U1", "22"), ("C7", "1")}
    assert all(n is None for n in [c.net_of("U1", "21")])               # DEC2 not connected
    assert c.instances["C4"].value == "100nF" and c.instances["C7"].value == "100pF"
    assert c.instances["C9"].value == "4.7uF" and c.instances["C11"].value == "22uF"


def test_dcdc_chain():
    c = build_fob()
    assert pads(c, "DCC") == {("U1", "31"), ("L2", "1")}
    assert pads(c, "DCDC_L") == {("L2", "2"), ("L3", "1")}
    assert pads(c, "DEC4") == {("L3", "2"), ("U1", "30"), ("C10", "1")}
    assert (c.instances["L2"].value, c.instances["L3"].value, c.instances["C10"].value) == ("10uH", "15nH", "1uF")


def test_crystal_and_rf_match():
    c = build_fob()
    assert pads(c, "XC1") == {("U1", "23"), ("Y1", "1"), ("C1", "1")}
    assert pads(c, "XC2") == {("U1", "24"), ("Y1", "3"), ("C2", "1")}
    assert pads(c, "ANT") == {("U1", "19"), ("C3", "1"), ("L1", "1")}     # 0.8 pF shunt, 3.9 nH series
    assert pads(c, "RF") == {("L1", "2"), ("CA1", "1"), ("R3", "1")}
    assert pads(c, "ANT_FEED") == {("R3", "2"), ("CA2", "1"), ("AE1", "1")}
    assert c.instances["CA1"].dnp and c.instances["CA2"].dnp
    assert {("AE1", "2"), ("AE1", "3"), ("AE1", "4")} <= pads(c, "GND")    # Johanson pads 2-4 GND


def test_ui_jumpers_and_debug():
    c = build_fob()
    assert pads(c, "P0_06") == {("U1", "6"), ("SW1", "2"), ("R2", "1")}
    assert c.instances["R2"].value == "1M" and ("R2", "2") in pads(c, "VBAT")
    assert pads(c, "LED_A") == {("R1", "2"), ("D1", "1")} and ("D1", "2") in pads(c, "GND")
    for bit, pin in enumerate(ID_BITS):
        jp = f"JP{bit + 1}"
        assert c.net_of(jp, "2") == "GND" and c.net_of(jp, "1") == pin.replace(".", "_")
    for pad, net in TC2030_PINS.items():
        assert c.net_of("J1", pad) == net
    assert c.net_of("U1", "16") == "NRESET" and c.net_of("U1", "14") == "SWO"


def test_breakout_carries_all_ten_spare_gpios():
    c = build_fob()
    assert c.net_of("J2", "1") == "VBAT" and c.net_of("J2", "2") == "GND"
    assert len(BREAKOUT) == 10
    gpio_pins = [n for n in PARTS["NRF"].pins if n.startswith("P0.")]
    assert len(gpio_pins) == 17
    assert all(c.net_of("U1", PARTS["NRF"].pins[n][0]) for n in gpio_pins)   # every GPIO wired


def test_every_nrf_pad_but_dec2_is_connected():
    """The EasyEDA symbol types every pin 'unspecified', so check() can't catch an unconnected
    power pin on U1: check them all here instead."""
    c = build_fob()
    loose = [p.number for p in PARTS["NRF"].footprint.pads if p.number and c.net_of("U1", p.number) is None]
    assert loose == ["21"]


def test_pins_h():
    h = pins_h()
    assert "#define FOB_PIN_BUTTON 6" in h and "#define FOB_PIN_LED 9" in h
    assert "#define FOB_PIN_ID_BIT2 15" in h
