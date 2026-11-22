import sys
from pathlib import Path

sys.path.insert(0, "/Users/hieutran/.gemini/antigravity/scratch/gamesir-g8-mod/pi32v2-isa")
import pi32v2isa as isa

table = isa.load()
BASE = 0x01E000C0

def disasm_func(bin_path, start_va, end_va):
    data = Path(bin_path).read_bytes()
    offset = start_va - BASE
    max_offset = min(len(data), end_va - BASE)
    pc = start_va
    lines = []
    while offset < max_offset:
        try:
            insn, values, length = isa.decode(table, data, offset)
            asm = isa.format(insn, values)
            hex_str = data[offset:offset+length].hex()
            lines.append(f"{pc:08x}:  {hex_str:12}  {asm}")
            offset += length
            pc += length
        except Exception as e:
            lines.append(f"{pc:08x}:  {data[offset:offset+2].hex():12}  <error: {e}>")
            offset += 2
            pc += 2
    return "\n".join(lines)

if __name__ == "__main__":
    mode = sys.argv[1] # x2s or g8
    start = int(sys.argv[2], 16)
    end = int(sys.argv[3], 16)
    bin_file = f"/Users/hieutran/.gemini/antigravity/scratch/gamesir-g8-mod/{mode}/app.bin"
    print(disasm_func(bin_file, start, end))
