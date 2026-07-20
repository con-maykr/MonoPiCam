"""
ir_filter.py — controls the StarlightEye's built-in IR-cut filter switch.

Vendored and refactored from Will Whang's original IRFilter script:
https://github.com/will127534/StarlightEye/blob/main/software/IRFilter
(StarlightEye project, MIT License)

Original behavior preserved: the filter switch is a CH32V003 acting as an
I2C device at address 0x34 (shared I2C bus with the CMOS sensor). Writing
0x01 enables the IR filter, 0x00 disables it.

Changes from the original:
- Refactored into an importable function (`set_ir_filter`) so it can be
  called directly from mpc.py, in addition to a standalone CLI entry point
  preserving the original --enable/--disable/--i2c-bus/--i2c-address flags.
- Bus/address are parameterized with defaults read from this file's
  constants rather than hardcoded, so mpc.py and the CLI share one source
  of truth.

IMPORTANT: confirm your actual I2C bus number before relying on the
default below — it depends on which CAM/DISP port the StarlightEye is
physically connected to. See MonoPiCam's README for the detection command.
"""

import argparse
import smbus

DEFAULT_I2C_BUS = 4        # confirm against your own wiring - see README
DEFAULT_I2C_ADDRESS = 0x34


def set_ir_filter(enable: bool, i2c_bus: int = DEFAULT_I2C_BUS,
                   i2c_address: int = DEFAULT_I2C_ADDRESS) -> None:
    """Enable or disable the StarlightEye's IR-cut filter.

    Args:
        enable: True to enable (engage) the IR filter, False to disable it.
        i2c_bus: I2C bus number the StarlightEye is wired to.
        i2c_address: I2C address of the filter switch (default 0x34).
    """
    bus = smbus.SMBus(i2c_bus)
    bus.write_byte(i2c_address, 0x01 if enable else 0x00)


def _main():
    parser = argparse.ArgumentParser(description="StarlightEye IR filter control")
    parser.add_argument("--enable", dest="enable", action="store_true",
                         help="Enable the IR filter")
    parser.add_argument("--disable", dest="enable", action="store_false",
                         help="Disable the IR filter")
    parser.set_defaults(enable=None)
    parser.add_argument("--i2c-bus", type=int, default=DEFAULT_I2C_BUS,
                         help=f"I2C bus (default: {DEFAULT_I2C_BUS})")
    parser.add_argument("--i2c-address", type=lambda x: int(x, 0), default=DEFAULT_I2C_ADDRESS,
                         help=f"I2C address in hex (default: {hex(DEFAULT_I2C_ADDRESS)})")
    args = parser.parse_args()

    if args.enable is None:
        parser.error("one of --enable or --disable is required")

    set_ir_filter(args.enable, args.i2c_bus, args.i2c_address)
    print(f"IR Filter {'enabled' if args.enable else 'disabled'}.")


if __name__ == "__main__":
    _main()