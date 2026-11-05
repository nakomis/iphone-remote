"""Parts catalogue: LCSC/EasyEDA footprints and symbols, plus local board-only footprints
(KiCad stock), keyed by role. Adapted from tinycrypt hardware/key-board."""
from dataclasses import dataclass
from pathlib import Path

from board.kicadlib import Footprint, load_footprint, load_symbol_pin_types, load_symbol_pins

HERE = Path(__file__).resolve().parent.parent
LCSC_FP = HERE / "footprints" / "lcsc.pretty"
LCSC_SYM = HERE / "footprints" / "lcsc.kicad_sym"
LOCAL_FP = HERE / "footprints" / "local.pretty"


@dataclass
class PartDef:
    key: str
    value: str
    lcsc: str | None         # None: a board-only footprint (test pads, mounting hole), never in BOM/CPL
    footprint: Footprint
    pins: dict
    pin_types: dict
    extended: bool
    tht: bool
    rotation_offset: float   # degrees added to placement rotation for JLCPCB CPL
    body: tuple              # (xmin, ymin, xmax, ymax): the part's real extent, for placement checks


# key: (value, lcsc, footprint file stem, symbol name, extended, rotation_offset)
# Footprint stems and symbol names are exactly what easyeda2kicad wrote. lcsc None means a local,
# board-only footprint from footprints/local.pretty. Symbol None means pin name = pad number
# (two-pin passives whose EasyEDA symbol couldn't be fetched share a fetched footprint of the same
# package). Every LCSC part was checked "Economic and Standard" on its JLC page, 5 Nov 2026.
_TABLE = {
    "NRF": ("nRF52810-QCAA-R", "C519278", "QFN-32_L5.0-W5.0-P0.50-BL-EP3.8", "NRF52810-QCAA-R", True, 0),
    "XTAL": ("32MHz CL8pF", "C718072", "CRYSTAL-SMD_4P-L2.0-W1.6-BL", "X201632MKB4SI", True, 0),
    "ANT": ("2450AT18D0100E", "C2917718", "ANT-SMD_4P-L3.2-W1.6", "2450AT18D0100E", True, 0),
    "BAT": ("MY-2032-12", "C964833", "BAT-SMD_MY-2032-12", "MY-2032-12", True, 0),
    "SW": ("TS-1187A-B-A-B", "C318884", "SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5", "TS-1187A-B-A-B", False, 0),
    "LED": ("KT-0603R red", "C2286", "LED-SMD_L1.6-W0.8-R-RD", "KT-0603R", False, 0),
    "C12P": ("12pF", "C1547", "C0402", "0402CG120J500NT", False, 0),
    "C0P8": ("0.8pF", "C327032", "C0402", "CC0402BRNPO9BNR80", True, 0),
    "C100N": ("100nF", "C1525", "C0402", "CL05B104KO5NNNC", False, 0),
    "C100P": ("100pF", "C1546", "C0402", "0402CG101J500NT", False, 0),
    "C4U7": ("4.7uF", "C19666", "C0603", "CL10A475KO8NNNC", False, 0),
    "C1U": ("1uF", "C15849", "C0603", "CL10A105KB8NNNC", False, 0),
    "C22U": ("22uF", "C45783", "C0805", "CL21A226MAQNNNE", False, 0),
    "L3N9": ("3.9nH", "C14033", "L0402", "SDCL1005C3N9STDF", True, 0),
    "L10U": ("10uH", "C1035", "C0603", None, False, 0),
    "L15N": ("15nH", "C27143", "L0402", None, True, 0),
    "R470": ("470R", "C25117", "R0402", None, False, 0),
    "R1M": ("1M", "C26083", "R0402", None, False, 0),
    "R0": ("0R", "C17168", "R0402", "0402WGF0000TCE", False, 0),
    # Not fitted (dnp): footprints for retuning the antenna match by hand.
    "CDNP": ("DNP", None, "C0402", None, False, 0),
    "JUMPER": ("Solder jumper", None, "SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm", None, False, 0),
    "HDR": ("2x6 1.27mm (unpopulated)", None, "PinHeader_2x06_P1.27mm_Vertical", None, False, 0),
    "TC2030": ("TC2030-CTX (SWD)", None, "Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical", None, False, 0),
}

# fetched-name -> our-name, per key.
ALIASES = {}

# Real extents where the footprint's courtyard is wrong: none yet.
BODY = {}

LCSC_3D = HERE / "footprints" / "lcsc.3dshapes"
MODEL_OVERRIDE = {}
MODEL_OFFSET = {}


def _load(key, row):
    value, lcsc, fp_stem, sym, extended, rot = row
    local = LOCAL_FP / f"{fp_stem}.kicad_mod"
    fp = load_footprint(local if local.exists() else LCSC_FP / f"{fp_stem}.kicad_mod")
    pins = {}
    if sym is None:     # footprint-only part: one passive pin per numbered pad, name = number
        pins = {p.number: [p.number] for p in fp.pads if p.number}
        pin_types = {n: "passive" for n in pins}
    else:
        alias = ALIASES.get(key, {})
        for name, nums in load_symbol_pins(LCSC_SYM, sym).items():
            pins.setdefault(alias.get(name, name), []).extend(nums)
        pin_types = load_symbol_pin_types(LCSC_SYM, sym)
    # Through-hole only if most numbered signal pads are drilled.
    numbered = [p for p in fp.pads if p.number]
    tht = bool(numbered) and sum(p.kind == "thru_hole" for p in numbered) * 2 > len(numbered)
    return PartDef(key, value, lcsc, fp, pins, pin_types, extended, tht, rot, BODY.get(key, fp.courtyard))


# Extended parts whose CPL rotation offset has been checked. EasyEDA-fetched footprints follow
# JLCPCB's own orientation convention, so their offset is 0. The final check is a look at
# JLCPCB's placement preview at order time.
ROTATION_CHECKED = {k for k, row in _TABLE.items() if row[4] and row[5] == 0}

PARTS = {k: _load(k, row) for k, row in _TABLE.items()}


def part(key):
    return PARTS[key]
