#!/usr/bin/env bash
# Fetch footprints + symbols for every LCSC part into footprints/lcsc.*
set -euo pipefail
cd "$(dirname "$0")"
PARTS=(
  C519278   # NRF (nRF52810-QCAA-R)
  C718072   # XTAL (YXC X201632MKB4SI, 32 MHz, CL 8 pF)
  C2917718  # ANT (Johanson 2450AT18D0100E)
  C964833   # BAT (MYOUNG MY-2032-12 CR2032 holder)
  C318884   # SW (TS-1187A-B-A-B)
  C2286     # LED (KT-0603R, red)
  C1547     # C12P
  C327032   # C0P8
  C1525     # C100N
  C1546     # C100P
  C19666    # C4U7 (0603)
  C15849    # C1U (0603)
  C45783    # C22U (0805)
  C14033    # L3N9
  C1035     # L10U (0603)
  C27143    # L15N
  C25117    # R470
  C26083    # R1M
  C17168    # R0
)
# easyeda.com's CloudFront returns 403 for easyeda2kicad's default User-Agent, so run it
# through a one-line wrapper that sends a neutral UA instead.
FAILED=()
for c in "${PARTS[@]}"; do
  # resumable: skip parts whose symbol is already in the library
  grep -q "\"$c\"" footprints/lcsc.kicad_sym 2>/dev/null && continue
  sleep 15   # be polite: easyeda.com rate-limits bursts with a 403
  .venv/bin/python -c '
import sys
from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
_init = EasyedaApi.__init__
def init(self):
    _init(self)
    self.headers["User-Agent"] = "iphone-remote-fetch"
EasyedaApi.__init__ = init
from easyeda2kicad.__main__ import main
sys.argv[0] = "easyeda2kicad"
sys.exit(main())
' --symbol --footprint --lcsc_id="$c" --output footprints/lcsc --overwrite || FAILED+=("$c")
done
if ((${#FAILED[@]})); then echo "FAILED: ${FAILED[*]}" >&2; exit 1; fi
