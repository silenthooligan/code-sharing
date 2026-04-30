#!/usr/bin/env python3
"""Enter ESP32-S3 ROM bootloader on a Nabu Casa ZBT-2 or ZWA-2 dongle from CLI.

The stock Nabu Casa USB-CDC bridge firmware (NabuCasa/zwave-esp-bridge,
including branch puddly/zbt2-final for the ZBT-2) listens for a "magic
baudrate sequence" — three USB CDC SET_LINE_CODING transitions in a row
at specific baud rates — and then drops into a `cmd>` prompt. Sending
the two ASCII bytes "BE" reboots the ESP32-S3 into ROM bootloader mode
where esptool can flash it.

Magic sequences (terminal baud is the rate the prompt speaks at):
    ZWA-2:  150 → 300 → 600    (cmd> prompt at 600 baud)
    ZBT-2:  150 → 300 → 1200   (cmd> prompt at 1200 baud)

This script tries the ZBT-2 sequence first, then falls back to ZWA-2.

Reference: home-assistant/zwa2-toolbox src/lib/esp-utils.ts (the JS the
official ZWA-2 web installer uses).

After this script returns, the device should disconnect and re-enumerate
as Espressif (303a:0009 USB-OTG ROM, or 303a:1001 USB-Serial-JTAG). Then:

    sudo chmod a+rw /dev/ttyACM*    # if you're not in dialout
    esptool --port /dev/ttyACM<N> --chip esp32s3 --before usb-reset \\
        --after hard-reset --baud 460800 write-flash -z \\
        --flash-size detect \\
        0x0      bootloader.bin \\
        0x8000   partitions.bin \\
        0x9000   ota_data_initial.bin \\
        0x10000  firmware.bin

If after the BE the device shows up as `Espressif ESP32-S3` (303a:0009)
and esptool fails with "No serial data received", do a Linux USB
unbind/rebind to refresh the kernel's CDC-ACM enumeration:

    BUS_ID=$(basename "$(readlink -f /sys/class/tty/ttyACM<N>/device/..)")
    echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/unbind
    sleep 1
    echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/bind

The device should come back as `Espressif USB JTAG/serial debug unit`
(303a:1001) and esptool's `--before usb-reset` will work cleanly.

Usage:
    pip install pyserial
    ./enter-esp-bootloader.py /dev/ttyACM0
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    import serial
except ImportError:
    print("Missing dependency: pip install pyserial", file=sys.stderr)
    sys.exit(2)

# Both known magic-baud sequences. Each entry: (label, [b1, b2, b3]).
# Try ZBT-2 first since it's the newer firmware. Only the matching variant
# triggers cmd> on a given dongle's stock firmware.
MAGIC_BAUDS_VARIANTS = [
    ("ZBT-2", [150, 300, 1200]),
    ("ZWA-2", [150, 300, 600]),
]
INTER_GAP = 0.1
CMD_PROMPT_TIMEOUT = 2.0


def try_variant(device: str, label: str, bauds: list[int]) -> bool:
    """Try one magic-baud variant. Returns True if BE was sent."""
    print(f"[{label}] magic sequence {bauds}")
    last = None
    for i, baud in enumerate(bauds):
        if last is not None:
            last.close()
            time.sleep(INTER_GAP)
        last = serial.Serial(device, baudrate=baud, timeout=0.3)

    s = last
    assert s is not None

    buf = b""
    deadline = time.monotonic() + CMD_PROMPT_TIMEOUT
    while time.monotonic() < deadline:
        chunk = s.read(64)
        if chunk:
            buf += chunk
            if b"cmd>" in buf:
                break

    if b"cmd>" not in buf:
        s.close()
        return False

    print(f"[{label}] cmd> prompt seen — sending BE")
    s.write(b"BE")
    s.flush()
    time.sleep(0.3)
    s.close()
    return True


def main(device: str) -> int:
    if not Path(device).exists():
        print(f"error: {device} does not exist", file=sys.stderr)
        return 2

    for label, bauds in MAGIC_BAUDS_VARIANTS:
        if try_variant(device, label, bauds):
            print()
            print("Device should now be in ESP32-S3 ROM bootloader mode.")
            print("Wait ~2s for re-enumeration, then run esptool. See script docstring.")
            return 0
        print(f"  no cmd> at {bauds}, trying next variant")
        time.sleep(0.3)

    print("error: no variant produced a cmd> prompt.", file=sys.stderr)
    print("hints:", file=sys.stderr)
    print("  - is the dongle still running stock USB-CDC bridge firmware?", file=sys.stderr)
    print("  - if you've already flashed ESPHome onto the ESP32-S3, use the", file=sys.stderr)
    print("    ESPHome dashboard's OTA path instead of this script.", file=sys.stderr)
    print("  - last resort: open the dongle and short GPIO0 to GND while", file=sys.stderr)
    print("    plugging in the USB cable.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
