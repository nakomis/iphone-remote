import pytest
from board.netlist import Circuit, check


def test_connect_and_lookup():
    c = Circuit()
    r1, r2 = c.add("R470"), c.add("R470")
    c.connect("A", (r1, "1"), (r2, "1"))
    c.connect("B", (r1, "2"), (r2, "2"))
    assert r1.ref == "R1" and r2.ref == "R2"
    assert c.net_of("R1", "1") == "A"
    assert check(c) == []


def test_pad_on_two_nets_is_reported():
    c = Circuit()
    r1, r2 = c.add("R470"), c.add("R470")
    c.connect("A", (r1, "1"), (r2, "1"))
    c.connect("B", (r1, "1"), (r2, "2"))
    assert any("two nets" in p for p in check(c))


def test_single_pad_net_is_reported():
    c = Circuit()
    r1 = c.add("R470")
    c.connect("LONELY", (r1, "1"))
    assert any("LONELY" in p for p in check(c))


def test_unknown_pin_raises():
    c = Circuit()
    r1 = c.add("R470")
    with pytest.raises(KeyError):
        c.connect("A", (r1, "nonsense"))


def _powered(c, dnp=False):
    """A resistor instance whose pins are re-typed power_in: this library's EasyEDA symbols type
    every pin 'unspecified', so the power-pin check needs a synthetic part to exercise it."""
    import dataclasses
    u = c.add("R470", dnp=dnp)
    u.part = dataclasses.replace(u.part, pin_types={"1": "power_in", "2": "power_in"})
    return u


def test_unconnected_power_pin_reported():
    c = Circuit()
    u = _powered(c)
    problems = check(c)
    assert any("power" in p and u.ref in p for p in problems)



def test_dnp_part_power_pins_not_required():
    c = Circuit()
    _powered(c, dnp=True)
    assert not any("power" in p for p in check(c))


def test_explicit_pad_must_belong_to_pin():
    c = Circuit()
    r1 = c.add("R470")
    with pytest.raises(KeyError):
        c.connect("A", (r1, "1", "99"))


def test_valid_explicit_pad_still_connects():
    c = Circuit()
    r1 = c.add("R470")
    c.connect("A", (r1, "1", "1"))
    assert c.net_of("R1", "1") == "A"


def test_explicit_ref_is_kept_and_auto_ref_skips_it():
    c = Circuit()
    r2 = c.add("R470", ref="R2")
    r_auto = c.add("R470")
    assert r2.ref == "R2"
    assert r_auto.ref != "R2"
    assert c.instances["R2"] is r2
    assert c.instances[r_auto.ref] is r_auto


def test_duplicate_explicit_ref_raises():
    c = Circuit()
    c.add("R470", ref="R1")
    with pytest.raises(ValueError):
        c.add("R470", ref="R1")


def test_two_output_pins_on_one_net_reported():
    from dataclasses import replace
    c = Circuit()
    r1, r2 = c.add("R470"), c.add("R470")
    r1.part = replace(r1.part, pin_types={"1": "output", "2": "input"})
    r2.part = replace(r2.part, pin_types={"1": "output", "2": "input"})
    c.connect("OUT", (r1, "1"), (r2, "1"))
    c.connect("B", (r1, "2"), (r2, "2"))
    assert any("several outputs" in p and "OUT" in p for p in check(c))
