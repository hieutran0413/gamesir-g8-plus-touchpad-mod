#!/usr/bin/env python3
"""
GameSir G8 Plus Firmware 2.20 Touchpad Mod (v2)
-----------------------------------------------
Patches the GameSir G8 Plus v2.20 Bluetooth firmware so that pressing
the Capture button (under D-Pad on the left) acts as the DualShock 4
Touchpad Click (Button 14) and triggers active touch contact (X=960, Y=470)
in PS4 / DualShock 4 wireless mode across iOS (PS Remote Play), Android, and PC.

Patches applied:
  1. Patch A (VA 0x01E03690, 34 bytes):
     Checks bits 5, 6, 7 of r10 (Capture, M, paddles) and sets Report Byte 6 bit 1
     (Touchpad Click) + bit 0 (Home/PS) + counter << 2.
  2. Patch B (VA 0x01E03758, 30 bytes):
     Branches to active touch handler (0x01E03776) if any of (r10 & 0xE0) != 0.
     Includes optimized inactive touch block.
  3. Patch C (VA 0x01E037A8, 12 bytes):
     Sets center touch coordinates: X=960 (0x3C0), Y=470 (0x1D6).
  4. Patch D (VA 0x01E11176, 2 bytes):
     Sets r0 = 1 in Report 1 handler for standard HID connections.

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
    head_entry = dec[0x00:0x20]
    head_hdr_crc, head_data_crc, head_addr, head_size = struct.unpack('<HHII', head_entry[:12])
    print(f"[*] app_area_head: addr=0x{head_addr:08x}, size={head_size}, data_crc=0x{head_data_crc:04x}")

    app_entry = dec[0x20:0x40]
    app_hdr_crc, app_data_crc, app_addr, app_size = struct.unpack('<HHII', app_entry[:12])
    print(f"[*] app.bin: offset=0x{app_addr:x}, size={app_size}, data_crc=0x{app_data_crc:04x}")

    # Extract app.bin
    app_bin = bytearray(dec[app_addr : app_addr + app_size])
    assert jl_crc16(app_bin) == app_data_crc, "Original app.bin CRC mismatch!"

    # 3. Apply Precision Patches
    print("[*] Applying precision patches to app.bin...")

    # Patch A: Report Byte 6 Touchpad Click + Home/PS (34 bytes at VA 0x01E03690 / offset 0x35D0)
    # Original: b8e80040588152ee9e08c0e1a40863e10200431960e10100301943e0a703d8ee2103
    # Patched:  588152ee9e08c0e1a40863e10e0003414322431960e10100301943e0a703d8ee2103
    patch_a_offset = 0x01E03690 - BASE_ADDR  # 0x35D0
    patch_a_orig = bytes.fromhex("b8e80040588152ee9e08c0e1a40863e10200431960e10100301943e0a703d8ee2103")
    patch_a_new = bytes.fromhex("588152ee9e08c0e1a40863e10e0003414322431960e10100301943e0a703d8ee2103")

    assert app_bin[patch_a_offset : patch_a_offset + len(patch_a_orig)] == patch_a_orig, (
        f"Patch A target mismatch at 0x{patch_a_offset:x}"
    )
    app_bin[patch_a_offset : patch_a_offset + len(patch_a_new)] = patch_a_new
    print(f"  [+] Patch A applied at VA 0x01E03690 (offset 0x{patch_a_offset:x}): Byte 6 Touchpad Click on r10 & 0xE0")

    # Patch B: Active Touch Branch on r10 & 0xE0 (30 bytes at VA 0x01E03758 / offset 0x3698)
    # Original: 5ae80d2a70e1011091165aee1f0843f080ff18413019984152ee2009049f
    # Patched:  61ffe0a00f0070e1011091165aee1f0818413027984152ee20090000049f
    patch_b_offset = 0x01E03758 - BASE_ADDR  # 0x3698
    patch_b_orig = bytes.fromhex("5ae80d2a70e1011091165aee1f0843f080ff18413019984152ee2009049f")
    patch_b_new = bytes.fromhex("61ffe0a00f0070e1011091165aee1f0818413027984152ee20090000049f")

    assert app_bin[patch_b_offset : patch_b_offset + len(patch_b_orig)] == patch_b_orig, (
        f"Patch B target mismatch at 0x{patch_b_offset:x}"
    )
    app_bin[patch_b_offset : patch_b_offset + len(patch_b_new)] = patch_b_new
    print(f"  [+] Patch B applied at VA 0x01E03758 (offset 0x{patch_b_offset:x}): Branch to active touch on r10 & 0xE0")

    # Patch C: Center Touchpad Coordinates (12 bytes at VA 0x01E037A8 / offset 0x36E8)
    # Original: 5b3f9b4173309b42432a9b43 (X=127, Y=173)
    # Patched:  73209b415b239b42433d9b43 (X=960, Y=470)
    patch_c_offset = 0x01E037A8 - BASE_ADDR  # 0x36E8
    patch_c_orig = bytes.fromhex("5b3f9b4173309b42432a9b43")
    patch_c_new = bytes.fromhex("73209b415b239b42433d9b43")

    assert app_bin[patch_c_offset : patch_c_offset + len(patch_c_orig)] == patch_c_orig, (
        f"Patch C target mismatch at 0x{patch_c_offset:x}"
    )
    app_bin[patch_c_offset : patch_c_offset + len(patch_c_new)] = patch_c_new
    print(f"  [+] Patch C applied at VA 0x01E037A8 (offset 0x{patch_c_offset:x}): Center coordinates X=960, Y=470")

    # Patch D: Set r0 = 1 in Report 1 handler (2 bytes at VA 0x01E11176 / offset 0x110B6)
    # Original: 4020 (r0 = 0)
    # Patched:  4021 (r0 = 1)
    patch_d_offset = 0x01E11176 - BASE_ADDR  # 0x110B6
    patch_d_orig = bytes.fromhex("4020")
    patch_d_new = bytes.fromhex("4021")

    assert app_bin[patch_d_offset : patch_d_offset + len(patch_d_orig)] == patch_d_orig, (
        f"Patch D target mismatch at 0x{patch_d_offset:x}"
    )
    app_bin[patch_d_offset : patch_d_offset + len(patch_d_new)] = patch_d_new
    print(f"  [+] Patch D applied at VA 0x01E11176 (offset 0x{patch_d_offset:x}): Set r0 = 1 in Report 1 handler")

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

    # Also save raw patched app.bin for inspection / git tracking
    app_out_path = output_zip_path.parent / "g8" / "app_mod.bin"
    app_out_path.write_bytes(app_bin)
    print(f"[+] Written patched app.bin: {app_out_path}")

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
