# GameSir G8 Plus Firmware 2.20 Touchpad Mod

Bản mod firmware dành cho tay cầm **GameSir G8 Plus (v2.20 Bluetooth)** giúp biến nút **Capture** (nút chụp ảnh nằm dưới D-Pad) thành nút **Touchpad Click** (Button 14 của DualShock 4) trong chế độ PS4 (`B + Home`).

Giải quyết triệt để vấn đề không thể mở bản đồ (Map) hoặc túi đồ (Inventory) khi chơi game PlayStation từ xa qua **Chiaki**, **PSPlay** hoặc **PS Remote Play** trên Android, PC và iOS.

---

## 1. Bối cảnh & Vấn đề

Khi kết nối GameSir G8 Plus ở chế độ PlayStation DualShock 4 (tổ hợp `B + Home`):
- Tay cầm nhận diện là **Sony DualShock 4 Wireless Controller** (VID: `0x054C`, PID: `0x05C4`).
- Tuy nhiên, khi bấm nút **Capture**, các ứng dụng Remote Play (Chiaki, PSPlay, PS Remote Play) **không nhận diện được nút Touchpad Click**.
- Trong các tựa game như *Ghost of Tsushima, The Witcher 3, Horizon Zero Dawn, God of War, Spider-Man*, nút Touchpad là phím bắt buộc để mở Map/Inventory.

---

## 2. Phân tích Kỹ thuật & Nguyên nhân Gốc rễ (Reverse Engineering)

### Kiến trúc Phần cứng & Firmware
- **MCU:** Dòng chip JieLi (JL BR28 / AC698x / JL701x).
- **Kiến trúc CPU:** PI32v2 (32-bit RISC ISA của JieLi).
- **Định dạng đóng gói:** JLFS2 (JieLi File System v2).
- **Mã hóa:** Thuật toán JieLi SFC Block Cipher (Key: `0xA80F`, Base Address: `0x01E000C0`).
- **Địa chỉ nạp RAM Gamepad State:** `0x6B00` (`27392`).

### Sơ đồ ánh xạ phím trong RAM (`0x6B00 + 612..614`):
- `Byte 612` (`0x6D64`): Phím mặt (A, B, X, Y), R1, R2.
- `Byte 614` (`0x6D66`): D-Pad (Up, Down, Left, Right), L1, L2.
- `Byte 613` (`0x6D65`):
  - Bit 0: Share / View / Minus
  - Bit 1: Options / Menu / Plus
  - Bit 2: L3
  - Bit 3: R3
  - Bit 4: Home (PS Button)
  - **Bit 5 (`0x20`): Capture Button (nút dưới D-Pad)**

### Trình tạo báo cáo DualShock 4 (`0x01E035B8`)
Hàm `0x01E035B8` chịu trách nhiệm tổng hợp dữ liệu báo cáo HID DualShock 4 tại `r2 + 929` (`r2 = 17120` = `0x42E0`):
- `r2 + 935` là **Byte 6 của DS4 Report** (Buttons 3):
  - Bit 0: Nút PS (`(Byte 613 & 0x10) >> 4 = 1`)
  - Bit 1: **Nút Touchpad Click** (`(Byte 613 & 0x20) >> 4 = 2`)
  - Bits 2..7: Rolling Frame Counter (`counter << 2`)
- `r2 + 963..975`: Gói dữ liệu mô phỏng chạm cảm ứng Touchpad (Finger touch packet tại tọa độ `X=127, Y=208`).

### Lỗi logic trên Firmware gốc của GameSir:
Tại địa chỉ `0x01E03690` trong `app.bin`:
```assembly
01e0368c: 54a2         r4 = r5 << 2        # r4 = frame counter
01e0368e: bc46         b[r3+6] = r4        # Ghi counter vào Byte 6 (Touchpad=0, PS=0)
01e03690: b8e80040     if (r8 != 0) {      # <-- LỖI TẠI ĐÂY! r8 là tham số r0 truyền vào
01e03694: 5881         r0 = r5 + 1
01e03696: 52ee9e08     b[r9+142] = r0
01e0369a: c0e1a408     r0 = r10 >> 4       # r10 là Byte 613
01e0369e: 63e10200     r3 = r0 & 0x2       # Bit 1 = Touchpad Click từ nút Capture!
01e036a2: 4319         r3 |= r4
01e036a4: 60e10100     r0 = r0 & 0x1       # Bit 0 = PS Button từ nút Home!
01e036a8: 3019         r0 |= r3
01e036aa: 43e0a703     r3 = 935
01e036ae: d8ee2103     b[r2+r3] = r0       # Ghi đè Byte 6 với Touchpad + PS + Counter!
                       }
```

Khi tay cầm kết nối Bluetooth với điện thoại Android / iOS / PC:
- Bluetooth HID chuẩn sử dụng **Report ID 1** (`0x01`).
- Trình truyền tin Bluetooth tại `0x01E11176` gọi `0x01E035B8` với **`r0 = 0`** (`r8 = 0`).
- Vì `r8 == 0`, điều kiện `if (r8 != 0)` trở thành **FALSE**!
- Toàn bộ khối lệnh từ `0x01E03694` đến `0x01E036AE` **bị bỏ qua hoàn toàn**!
- Hậu quả: `b[r2+935]` (Byte 6) luôn có Bit 1 (Touchpad Click) = 0 và Bit 0 (PS Button) = 0 khi gửi qua Bluetooth Report 1.

---

## 3. Nội dung Bản Mod

1. **Patch 1 (Địa chỉ VA `0x01E03690`, offset `0x35D0` trong `app.bin`):**
   - Gốc: `B8 E8 00 40` (`if (r8 != 0) {`)
   - Mod: `00 00 00 00` (`nop; nop`)
   - *Tác dụng:* Đoạn mã gán nút Capture thành Touchpad Click và nút Home thành PS Button chạy **vô điều kiện trên mọi báo cáo**.
2. **Patch 2 (Địa chỉ VA `0x01E11176`, offset `0x110B6` trong `app.bin`):**
   - Gốc: `40 20` (`r0 = 0`)
   - Mod: `40 21` (`r0 = 1`)
   - *Tác dụng:* Truyền `r0 = 1` cho hàm xử lý báo cáo Bluetooth Report 1.
3. **Tính toán lại Checksum:**
   - Cập nhật `data_crc` và `hdr_crc` của `app.bin` theo thuật toán CRC16-CCITT (poly `0x1021`, init `0x0000`).
   - Cập nhật `data_crc` (`crc16(area[32:])`) và `hdr_crc` cho partition `app_area_head`.
   - Tái mã hóa toàn bộ bằng thuật toán JieLi SFC Block Cipher (Key `0xA80F`).

---

## 4. Cấu trúc Thư mục Workspace

```
.
├── g8/
│   ├── app.bin                                     # Firmware app đã giải mã (gốc)
│   ├── ota.bin                                     # Firmware OTA gốc (393,908 bytes)
│   ├── ota_mod_touchpad.bin                        # Firmware OTA đã mod & mã hóa lại
│   └── ota.bin_unpack/
│       ├── decrypted.bin                           # JLFS2 container đã giải mã
│       └── jlfw.yaml                               # Metadata unpack
├── x2s/
│   ├── app.bin                                     # Firmware X2s đã giải mã (đối chứng)
│   └── ota.bin                                     # Firmware X2s gốc
├── jl-misctools/                                   # Bộ công cụ xử lý firmware JieLi (cipher, crc, jlfs)
├── pi32v2-isa/                                     # Bộ disassembler / codec cho kiến trúc PI32v2
├── jielie/                                         # Tài liệu định dạng firmware JieLi
├── dex_files/                                      # Dex đã bung từ GameSir App
├── apk_libs/                                       # Thư viện native đã trích xuất từ GameSir App
├── mod_firmware.py                                 # Script tự động giải mã, patch & đóng gói OTA
├── g8-bluetooth-firmware-2.20-mod-touchpad.zip     # Bản zip release sẵn sàng nạp OTA
└── README.md
```

---

## 5. Hướng dẫn Tự Rebuild Firmware

Yêu cầu môi trường Python 3.9+:
```bash
pip install -r requirements.txt
python3 mod_firmware.py
```
Script sẽ tự động đọc `g8/ota.bin`, áp dụng các byte patch, tính lại CRC16, mã hóa JieLi SFC và xuất ra `g8-bluetooth-firmware-2.20-mod-touchpad.zip`.

---

## 6. Hướng dẫn Nạp Firmware & Sử dụng

1. **Chuẩn bị:**
   - Giải nén hoặc sử dụng trực tiếp file `ota.bin` trong `g8-bluetooth-firmware-2.20-mod-touchpad.zip`.
   - Sử dụng ứng dụng GameSir (Android/iOS) hoặc công cụ nạp JieLi OTA để nạp file vào tay cầm.
2. **Khởi động chế độ DualShock 4:**
   - Nhấn giữ tổ hợp phím **`B + Home`** cho đến khi đèn báo hiệu chuyển sang chế độ DualShock 4 (đèn xanh dương / trắng).
   - Ghép đôi Bluetooth với điện thoại, máy tính bảng hoặc PC.
3. **Trải nghiệm:**
   - Bấm nút **Capture** (nằm ngay dưới phím D-Pad) -> Nhận diện ngay lập tức là **Touchpad Click (Button 14)**.
   - Thao tác mở Map / Inventory trong Chiaki, PSPlay, PS Remote Play hoạt động mượt mà và chuẩn xác.

---

## License & Tuyên bố miễn trừ trách nhiệm
- Dự án này phục vụ mục đích nghiên cứu kỹ thuật và sửa lỗi tương thích phần cứng cho người dùng cuối.
- Các công cụ disassembler và thuật toán SFC thuộc về các tác giả trong cộng đồng nguồn mở JieLi reverse engineering.
