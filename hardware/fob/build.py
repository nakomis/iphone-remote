#!/usr/bin/env python3
"""Fob board generator (IREM-3 stage: the circuit).

    ./.venv/bin/python build.py

Builds the circuit from board/fob_board.py, runs the netlist checks, and writes out/fob/:
bom.csv (JLCPCB format), netlist.txt (every net and the pads on it) and pins.h (for the
firmware). Placement, routing, DRC and gerbers arrive with the layout (IREM-4), following the
tinycrypt key-board pipeline this is adapted from."""
from pathlib import Path

from board.fab import write_bom
from board.fob_board import build_fob, pins_h
from board.netlist import check

HERE = Path(__file__).resolve().parent


def netlist_txt(c):
    lines = []
    for net in sorted(c.nets):
        pads = ", ".join(f"{r}.{p}" for r, p in sorted(c.nets[net]))
        lines.append(f"{net:10} {pads}")
    dnp = sorted(r for r, i in c.instances.items() if i.dnp)
    return "\n".join(lines) + f"\n\nNot fitted: {', '.join(dnp)}\n"


def main():
    c = build_fob()
    problems = check(c)
    if problems:
        raise SystemExit("\n".join(problems))
    out = HERE / "out" / "fob"
    out.mkdir(parents=True, exist_ok=True)
    write_bom(c, out / "bom.csv")
    (out / "netlist.txt").write_text(netlist_txt(c))
    (out / "pins.h").write_text(pins_h())
    fitted = [i for i in c.instances.values() if not i.dnp and i.part.lcsc]
    ext = sorted({i.part.lcsc for i in fitted if i.part.extended})
    print(f"{len(c.instances)} parts ({len(fitted)} assembled), {len(c.nets)} nets; "
          f"{len(ext)} extended parts: {', '.join(ext)}")
    print(f"wrote {out}/bom.csv, netlist.txt, pins.h")


if __name__ == "__main__":
    main()
