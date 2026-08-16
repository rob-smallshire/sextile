#!/usr/bin/env bash
#
# Serve the hero title frame and bridge it to an emulated modem, so a BBC Micro
# under Beebium (or BeebEm, or real hardware with a WiFi modem) can dial in and
# be photographed for docs/images/sextile-hero.png.
#
# This does the two long-running steps for you -- serving on 6850 and bridging
# with tcpser -- and prints the emulator steps. Leave it running, capture the
# screen from the emulator, then Ctrl-C here.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

PORT="${PORT:-6850}"

echo "== serving the hero on port $PORT (line held open for the photo) =="
uv run sextile serve examples.hero:app --port "$PORT" --idle-timeout 0 &
SERVE=$!
trap 'kill "$SERVE" "${TCPSER:-}" 2>/dev/null || true' EXIT
sleep 1

echo "== bridging TCP to an emulated modem with tcpser =="
tcpser -v 25232 -s 9600 -l 4 -t sS -n "1=localhost:$PORT" &
TCPSER=$!

cat <<'STEPS'

Now, in the emulator (Beebium shown; BeebEm has its own IP232 support):

  ./beebium-model-b start \
      --sideways 13:rom:/path/to/commstar_1_40_SN882A.rom \
      --ip232-serial host=localhost:port=25232 \
      --machine-name "Sextile" --advertise

  then File > Connect... > Sextile, and at the BBC keyboard:

  *COMMSTAR       start the comms ROM
  #               switch to Prestel emulation
  C               enter chat mode
  ATDT1  CTRL-M   dial phonebook entry 1 (CTRL-M, not RETURN: RETURN sends 0x5F)

The hero frame appears; photograph the emulator window, crop to the screen, and
save it as docs/images/sextile-hero.png. Ctrl-C here when done.

STEPS
wait
