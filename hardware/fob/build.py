#!/usr/bin/env python3
"""Fob board generator (IREM-3 stage: the circuit).

    ./.venv/bin/python build.py

Builds the circuit from board/fob_board.py, runs the netlist checks, and writes out/fob/:
bom.csv (JLCPCB format), netlist.txt (every net and the pads on it) and pins.h (for the
firmware). Placement, routing, DRC and gerbers arrive with the layout (IREM-4), following the
tinycrypt key-board pipeline this is adapted from."""
from pathlib import Path

import argparse
import json
import subprocess

from board.cleanup import prune
from board.fab import fab, write_bom, write_cpl
from board.route import route
from board.fob_board import build_fob, pins_h
from board import fob_layout as fl
from board.kicad_pcb import write_board
from board.netlist import check

KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
STEM = "iphone-remote-fob"

HERE = Path(__file__).resolve().parent


def netlist_txt(c):
    lines = []
    for net in sorted(c.nets):
        pads = ", ".join(f"{r}.{p}" for r, p in sorted(c.nets[net]))
        lines.append(f"{net:10} {pads}")
    dnp = sorted(r for r, i in c.instances.items() if i.dnp)
    return "\n".join(lines) + f"\n\nNot fitted: {', '.join(dnp)}\n"


def drc(board, out):
    """KiCad DRC (refilling zones into the board); returns (errors, warnings)."""
    subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--format", "json",
                    "--severity-all", "-o", str(out / "drc.json"), str(board)], check=True, capture_output=True)
    d = json.loads((out / "drc.json").read_text())
    bad = [f"unconnected: {' / '.join(i['description'] for i in u['items'])}" for u in d["unconnected_items"]]
    bad += [f"{v['type']}: {v['description']} [{'; '.join(i['description'] for i in v.get('items', []))}]"
            for v in d["violations"] if v["severity"] == "error"]
    warn = [v for v in d["violations"] if v["severity"] != "error"]
    return bad, warn


def layout(c, out, do_route, passes):
    p = fl.place_fob(c)
    hand_t, hand_v = fl.rf_hand_route(c)
    fixed = hand_v + fl.edge_vias() + fl.ep_vias()
    tracks, vias = list(hand_t), list(fixed)
    if do_route:
        rt, rv = route(c, p, out / "tmp", passes=passes, layers=2, route_area=fl.route_area(),
                       fixed_vias=fixed, fixed_tracks=hand_t, layer_keepouts=fl.layer_keepouts(),
                       skip_nets=("GND",), log="/tmp/irem-fob-route.log")
        tracks, vias = prune(c, p, tracks + rt, fixed + rv, keep=fixed)
        stitch = fl.stitch_vias(c, p, tracks, vias, pitch=1.5, avoid=[fl.ANT_BOX, fl.ART_BOX, fl.CREDIT_BOX])
        print(f"stitching: {len(stitch)} GND vias")
        vias += stitch
    board = out / f"{STEM}.kicad_pcb"
    write_board(c, p, board, tracks, vias, layers=2, keepouts=fl.keepouts(), silk=fl.silk(c), art=fl.art(), pad_extra=fl.pad_extra(c),
                mask="White", silkscreen="Black",
                hide_refs=set(c.instances))
    run = lambda *a: subprocess.run([KICAD_CLI, *a], check=True, capture_output=True, text=True)
    run("pcb", "export", "svg", "--layers", "F.Cu,F.Silkscreen,Edge.Cuts", "--mode-single",
        "--fit-page-to-board", "-o", str(out / f"{STEM}-front.svg"), str(board))
    run("pcb", "render", "--side", "top", "--width", "1400", "--height", "2400", "--quality", "basic",
        "-o", str(out / f"{STEM}-top.png"), str(board))
    return board, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", action="store_true", help="also write the board (placement only)")
    ap.add_argument("--route", action="store_true", help="route, check DRC and write the fab files")
    ap.add_argument("--passes", type=int, default=100)
    a = ap.parse_args()
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
    if a.layout or a.route:
        board, p = layout(c, out, a.route, a.passes)
        bad, warn = drc(board, out)
        kinds = {}
        for v in warn:
            kinds[v["type"]] = kinds.get(v["type"], 0) + 1
        print(f"wrote {board}: {len(bad)} DRC errors/unconnected, {len(warn)} warnings {kinds}")
        if a.route:
            if bad:
                raise SystemExit("DRC failed:\n" + "\n".join(bad))
            write_cpl(c, p, out / "cpl.csv")
            fab(board, out, layers=2)
            print(f"fab outputs in {out}")


if __name__ == "__main__":
    main()
