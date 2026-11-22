#!/usr/bin/env python3
"""
GameSir G8 Plus Firmware 2.20 Touchpad Mod
------------------------------------------
Patches the GameSir G8 Plus v2.20 Bluetooth firmware so that pressing
the Capture button (under D-Pad) acts as the DualShock 4 Touchpad Click
(Button 14) in PS4 / DualShock 4 wireless mode across all connections
(Standard Android HID Bluetooth, Extended Bluetooth Report 17, and USB).

Author: Hieu Tran & Antigravity
"""

import os
import sys
import struct
import zipfile
from pathlib import Path

# Add local jl-misctools to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "jl-misctools" / "firmware"))

from jltech.crc import jl_crc16
import jltech.cipher as cipher

BASE_ADDR = 0x01E000C0
SFC_KEY = 0xA80F


def patch_firmware(ota_input_path: Path, output_zip_path: Path):
    print(f"[*] Reading original OTA: {ota_input_path}")
    ota_data = bytearray(ota_input_path.read_bytes())
    orig_len = len(ota_data)
    print(f"[*] Original OTA size: {orig_len} bytes")

    # 1. Decrypt JLFS2 image using JieLi SFC cipher
    print(f"[*] Decrypting JLFS2 container with key 0x{SFC_KEY:04x}...")
    dec = bytearray(cipher.cipher_bytes(cipher.jl_sfc_cipher, ota_data, 0, SFC_KEY))

    # 2. Parse JLFS2 Entries
    # Entry 0: app_area_head (0x00..0x20)
    # Entry 1: app.bin        (0x20..0x40)
    head_entry = dec[0x00:0x20]
    head_hdr_crc, head_data_crc, head_addr, head_size = struct.unpack('<HHII', head_entry[:12])
    print(f"[*] app_area_head: addr=0x{head_addr:08x}, size={head_size}, data_crc=0x{head_data_crc:04x}")

    app_entry = dec[0x20:0x40]
    app_hdr_crc, app_data_crc, app_addr, app_size = struct.unpack('<HHII', app_entry[:12])
    print(f"[*] app.bin: offset=0x{app_addr:x}, size={app_size}, data_crc=0x{app_data_crc:04x}")

    # Extract app.bin
    app_bin = bytearray(dec[app_addr : app_addr + app_size])
    assert jl_crc16(app_bin) == app_data_crc, "Original app.bin CRC mismatch!"

    # 3. Apply Patches
    print("[*] Applying precision patches to app.bin...")

    # Patch 1: Remove condition 'if (r8 != 0)' at 0x01e03690 (offset 0x35d0 in app.bin)
    # Original: b8 e8 00 40 (if (r8 != 0) {)
    # Patched:  00 00 00 00 (nop; nop)
    # Effect: Touchpad Click (Capture bit) & PS button (Home bit) are written to report byte 6 unconditionally
    patch1_offset = 0x01E03690 - BASE_ADDR  # 0x35d0
    patch1_orig = bytes([0xB8, 0xE8, 0x00, 0x40])
    patch1_new = bytes([0x00, 0x00, 0x00, 0x00])

    assert app_bin[patch1_offset : patch1_offset + 4] == patch1_orig, (
        f"Patch 1 target mismatch at 0x{patch1_offset:x}: "
        f"found {app_bin[patch1_offset:patch1_offset+4].hex()}, expected {patch1_orig.hex()}"
    )
    app_bin[patch1_offset : patch1_offset + 4] = patch1_new
    print(f"  [+] Patch 1 applied at VA 0x01E03690 (offset 0x{patch1_offset:x}): NOP out 'if (r8 != 0)'")

    # Patch 2: Set r0 = 1 instead of r0 = 0 before calling report generator in Report 1 handler
    # At 0x01E11176 (offset 0x110b6 in app.bin)
    # Original: 40 20 (r0 = 0)
    # Patched:  40 21 (r0 = 1)
    patch2_offset = 0x01E11176 - BASE_ADDR  # 0x110b6
    patch2_orig = bytes([0x40, 0x20])
    patch2_new = bytes([0x40, 0x21])

    assert app_bin[patch2_offset : patch2_offset + 2] == patch2_orig, (
        f"Patch 2 target mismatch at 0x{patch2_offset:x}: "
        f"found {app_bin[patch2_offset:patch2_offset+2].hex()}, expected {patch2_orig.hex()}"
    )
    app_bin[patch2_offset : patch2_offset + 2] = patch2_new
    print(f"  [+] Patch 2 applied at VA 0x01E11176 (offset 0x{patch2_offset:x}): Set r0 = 1")

    # 4. Put patched app.bin back into JLFS image
    dec[app_addr : app_addr + app_size] = app_bin

    # 5. Recalculate checksums for app.bin entry
    new_app_data_crc = jl_crc16(app_bin)
    struct.pack_into('<H', dec, 0x22, new_app_data_crc)
    new_app_hdr_crc = jl_crc16(dec[0x22:0x40])
    struct.pack_into('<H', dec, 0x20, new_app_hdr_crc)
    print(f"[*] Updated app.bin entry: data_crc=0x{new_app_data_crc:04x}, hdr_crc=0x{new_app_hdr_crc:04x}")

    # 6. Recalculate checksums for app_area_head entry
    new_head_data_crc = jl_crc16(dec[32:head_size])
    struct.pack_into('<H', dec, 0x02, new_head_data_crc)
    new_head_hdr_crc = jl_crc16(dec[0x02:0x20])
    struct.pack_into('<H', dec, 0x00, new_head_hdr_crc)
    print(f"[*] Updated app_area_head entry: data_crc=0x{new_head_data_crc:04x}, hdr_crc=0x{new_head_hdr_crc:04x}")

    # 7. Re-encrypt container with JieLi SFC cipher
    print(f"[*] Re-encrypting JLFS2 container with key 0x{SFC_KEY:04x}...")
    ota_patched = cipher.cipher_bytes(cipher.jl_sfc_cipher, dec, 0, SFC_KEY)
    assert len(ota_patched) == orig_len, "Patched OTA length differs from original!"

    # 8. Verify re-decryption and checksums
    print("[*] Verifying encrypted output...")
    verify_dec = cipher.cipher_bytes(cipher.jl_sfc_cipher, ota_patched, 0, SFC_KEY)
    assert verify_dec == dec, "Verification failed: decrypted bytes differ!"
    assert jl_crc16(verify_dec[app_addr : app_addr + app_size]) == new_app_data_crc
    assert jl_crc16(verify_dec[0x22:0x40]) == new_app_hdr_crc
    assert jl_crc16(verify_dec[32:head_size]) == new_head_data_crc
    assert jl_crc16(verify_dec[0x02:0x20]) == new_head_hdr_crc
    print("[+] All verification checks PASSED successfully!")

    # 9. Write outputs
    bin_out_path = output_zip_path.parent / "g8" / "ota_mod_touchpad.bin"
    bin_out_path.write_bytes(ota_patched)
    print(f"[+] Written patched binary: {bin_out_path}")

    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ota.bin", ota_patched)
    print(f"[+] Created flashable ZIP: {output_zip_path} ({len(ota_patched)} bytes in ota.bin)")


def main():
    ota_in = SCRIPT_DIR / "g8" / "ota.bin"
    zip_out = SCRIPT_DIR / "g8-bluetooth-firmware-2.20-mod-touchpad.zip"
    if not ota_in.exists():
        print(f"[-] Error: {ota_in} not found!")
        sys.exit(1)
    patch_firmware(ota_in, zip_out)


if __name__ == "__main__":
    main()
