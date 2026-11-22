# GameSir G8 Plus Firmware 2.20 Touchpad Mod (v2)

Bản mod firmware dành cho tay cầm **GameSir G8 Plus (v2.20 Bluetooth)** giúp biến nút **Capture** (và nút M / Back paddles) thành nút **Touchpad Click** (Button 14 của DualShock 4) cùng tọa độ chạm cảm ứng ở chính giữa Touchpad (X=960, Y=470) trong chế độ PS4 (`B + Home`).

Tương thích hoàn hảo với **PS Remote Play**, **Chiaki**, **PSPlay** trên **iPhone / iOS**, **Android**, và **PC**.

---

## 1. Bối cảnh & Phân tích Nguyên nhân

### Trải nghiệm thực tế
- Trên tay cầm **GameSir X2s** (firmware v1.11), nút Capture hoạt động bình thường như Touchpad trong PS Remote Play trên iPhone/iOS.
- Tuy nhiên trên **GameSir G8 Plus** (firmware gốc v2.20), khi kết nối iPhone ở chế độ DS4 (`B + Home`), nút Capture hoàn toàn không mở được Map/Inventory trong PS Remote Play.

### Nguyên nhân gốc rễ (Reverse Engineering PI32v2):
1. **Khác biệt phần cứng giữa G8 Plus và X2s:**
   - Trên X2s chỉ có 1 nút phụ duy nhất (Capture), phần cứng quét vào `b[r9+597]` bit 5 (`r10 & 32`).
   - Trên G8 Plus có tới 4 nút phụ: **Capture, M, L4, R4**. Phần cứng quét các nút phụ vào các bit 5, 6, 7 của `b[r9+613]` (`r10`). Firmware gốc chỉ kiểm tra bit 5 (`r10 & 32`). Do đó khi nhấn Capture hoặc M, nếu rơi vào bit 6 (`0x40`) hoặc bit 7 (`0x80`), firmware gốc bỏ qua hoàn toàn.
2. **Yêu cầu của iOS PS Remote Play đối với DualShock 4 qua Bluetooth:**
   - Trên iOS, Apple Game Controller framework giao tiếp bằng **Extended Bluetooth Report 17 (`0x11`, 79 bytes)** kèm mã kiểm tra CRC32.
   - Để kích hoạt nút Touchpad trong game PS4/PS5, iOS không chỉ đọc trạng thái nút nhấn vật lý ở **Byte 6 (bit 1 = Touchpad Click)** mà còn bắt buộc phải có gói dữ liệu cảm ứng chạm **Touch 1 Active (`Touch ID bit 7 = 0`)** tại Byte 34..37.
   - Nếu không có gói chạm cảm ứng hoặc bit 7 vẫn là `0x80` (Inactive/No finger), PS Remote Play sẽ coi là không có ngón tay đặt trên Touchpad và không nhận diện lệnh click.
3. **Tọa độ chạm cảm ứng (Coordinates):**
   - Firmware gốc hardcode tọa độ `X=127, Y=173`, nằm ở góc trên cùng bên trái của Touchpad (độ phân giải 1920x942).
   - Nhiều tựa game trên PlayStation chia Touchpad thành 2 hoặc 3 vùng riêng biệt (Click bên trái = Map, Click bên phải = Inventory, Click ở giữa = Menu). Tọa độ rìa ngoài dễ bị hiểu nhầm thành edge swipe hoặc lệch vùng click.

---

## 2. Chi tiết 4 Precision Patches trong Bản Mod v2

| Patch | Địa chỉ VA | Offset `app.bin` | Độ dài | Mô tả |
|---|---|---|---|---|
| **Patch A** | `0x01E03690` | `0x35D0` | 34 bytes | Kiểm tra `r10 & 0xE0` (bits 5, 6, 7). Nếu bất kỳ nút phụ nào (Capture / M / Paddles) được nhấn, set Bit 1 của Report Byte 6 (Touchpad Click) + Bit 0 (Home/PS) + counter. |
| **Patch B** | `0x01E03758` | `0x3698` | 30 bytes | Lệnh rẽ nhánh 48-bit `if ((r10 & 0xE0) != 0) goto 30` nhảy thẳng tới nhánh kích hoạt Touch 1 Active (xóa bit 7, gán Touch ID hoạt động). |
| **Patch C** | `0x01E037A8` | `0x36E8` | 12 bytes | Đặt tọa độ chạm về chính giữa tâm Touchpad: **X = 960 (0x3C0), Y = 470 (0x1D6)** (`b[r1+1]=192, b[r1+2]=99, b[r1+3]=29`). |
| **Patch D** | `0x01E11176` | `0x110B6` | 2 bytes | Gán `r0 = 1` trong Report 1 handler phục vụ kết nối Bluetooth chuẩn trên Android HID / PC. |

---

## 3. Cấu trúc Workspace & Build

```
.
├── g8/
│   ├── app.bin                                     # Firmware app gốc đã giải mã
│   ├── app_mod.bin                                 # Firmware app đã patch
│   ├── ota.bin                                     # Firmware OTA gốc
│   └── ota_mod_touchpad.bin                        # Firmware OTA đã patch & mã hóa SFC
├── g8-bluetooth-firmware-2.20-mod-touchpad.zip     # File ZIP flash qua GameSir App
├── mod_firmware.py                                 # Script giải mã, patch, tính CRC16 & đóng gói
├── disasm_helper.py                                # PI32v2 disassembler helper
└── x2s/                                            # Firmware gốc GameSir X2s (Reference)
```

### Cách build lại firmware:
```bash
# Kích hoạt môi trường python
./venv/bin/python3 mod_firmware.py
```

---

## 4. Hướng dẫn Flash Firmware vào GameSir G8 Plus

1. Mở ứng dụng **GameSir** trên điện thoại (Android).
2. Kết nối tay cầm GameSir G8 Plus qua Bluetooth.
3. Chọn tính năng **Firmware Update** / **Local Update** (Nâng cấp từ file cục bộ).
4. Chọn file `g8-bluetooth-firmware-2.20-mod-touchpad.zip` (đã được copy vào `/sdcard/Download/`).
5. Đợi quá trình nạp đạt 100% và tay cầm tự khởi động lại.
6. Nhấn tổ hợp `B + Home` để kết nối lại chế độ DualShock 4 với iPhone / Android / PC và vào game test nút Touchpad.
