#!/usr/bin/env python3
"""
Targeted analysis of key regions in the .tn6 file.
Focus: records 35-36, records 98-110 (marker region), the header area, and the tail.
"""
import struct
import sys
import io
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

FILE_PATH = r"D:\PythonWorkSpace\AutoRunFeiShuSheet\temp\123.tn6"

with open(FILE_PATH, 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes (0x{len(data):x})")
print(f"64-byte records: {len(data)//64}, remainder: {len(data)%64}")

# Focus 1: Records 34-40 (transition region)
print("\n" + "="*80)
print("FOCUS 1: Records 34-40 (transition from formula metadata to compiled data)")
print("="*80)
for i in range(34, 41):
    off = i * 64
    chunk = data[off:off+64]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"  rec{i:4d} 0x{off:04x}: {hex_str}")
    print(f"  {'':8s} {'':8s}  {ascii_str}")

# Focus 2: Records 95-105 (where the marker 234b04de8ac7eb38 starts)
print("\n" + "="*80)
print("FOCUS 2: Records 95-105 (marker region start)")
print("="*80)
for i in range(95, 106):
    off = i * 64
    chunk = data[off:off+64]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"  rec{i:4d} 0x{off:04x}: {hex_str}")
    print(f"  {'':8s} {'':8s}  {ascii_str}")

# Focus 3: Records around 0x1880 (0x1880 // 64 = 98)
print("\n" + "="*80)
print("FOCUS 3: Detailed analysis of the marker region")
print("="*80)

# Check what's at offset 0x1880
marker = bytes.fromhex('234b04de8ac7eb38')
pos = 0
first_marker = None
while True:
    pos = data.find(marker, pos)
    if pos == -1:
        break
    if first_marker is None:
        first_marker = pos
    pos += 1
print(f"  First occurrence of '234b04de8ac7eb38': 0x{first_marker:04x} (record {first_marker//64})")

# Focus 4: The null record (record 50 = 0xC80)
print("\n" + "="*80)
print("FOCUS 4: Record 50 (all-null record)")
print("="*80)
off = 50 * 64
chunk = data[off:off+64]
hex_str = ' '.join(f'{b:02x}' for b in chunk)
print(f"  rec  50 0x{off:04x}: {hex_str}")
is_all_null = all(chunk[i:i+8] == bytes.fromhex('00f736f388946906') for i in range(0, 64, 8))
print(f"  Is all null pattern (8-byte repeating): {is_all_null}")

# Focus 5: Records 82-83 (all-zero block start)
print("\n" + "="*80)
print("FOCUS 5: All-zero block (records 82-95)")
print("="*80)
for i in range(82, 96):
    off = i * 64
    chunk = data[off:off+64]
    all_zero = all(b == 0 for b in chunk)
    if not all_zero:
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"  rec{i:4d} 0x{off:04x}: {hex_str}")
        print(f"  {'':8s} {'':8s}  {ascii_str}")
    else:
        print(f"  rec{i:4d} 0x{off:04x}: ALL ZEROS")

# Focus 6: Last few records + remainder
print("\n" + "="*80)
print("FOCUS 6: End of file")
print("="*80)
total_recs = len(data) // 64
for i in range(max(0, total_recs - 5), total_recs + 1):
    off = i * 64
    if off >= len(data):
        break
    chunk = data[off:off+64]
    hex_str = ' '.join(f'{b:02x}' for b in chunk)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f"  rec{i:4d} 0x{off:04x}: {hex_str}")
    print(f"  {'':8s} {'':8s}  {ascii_str}")

# Remainder
remainder_start = total_recs * 64
if remainder_start < len(data):
    remainder = data[remainder_start:]
    hex_str = ' '.join(f'{b:02x}' for b in remainder)
    print(f"  REMAIN 0x{remainder_start:04x}: ({len(remainder)} bytes) {hex_str}")

# Focus 7: XOR decode the data region (records 35+) with null pattern key
print("\n" + "="*80)
print("FOCUS 7: XOR decode records 35-45 with null pattern key")
print("="*80)
key = bytes.fromhex('00f736f388946906')
for i in range(35, 46):
    off = i * 64
    chunk = data[off:off+64]
    decoded = bytes(chunk[j] ^ key[j % 8] for j in range(64))
    hex_str = ' '.join(f'{b:02x}' for b in decoded)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in decoded)
    print(f"  rec{i:4d} decoded: {hex_str}")
    print(f"  {'':8s} {'':12s}  {ascii_str}")

# Focus 8: XOR decode the marker records (100+) with null pattern key
print("\n" + "="*80)
print("FOCUS 8: XOR decode records 98-105 with null pattern key")
print("="*80)
for i in range(98, 106):
    off = i * 64
    chunk = data[off:off+64]
    decoded = bytes(chunk[j] ^ key[j % 8] for j in range(64))
    hex_str = ' '.join(f'{b:02x}' for b in decoded)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in decoded)
    print(f"  rec{i:4d} decoded: {hex_str}")
    print(f"  {'':8s} {'':12s}  {ascii_str}")

# Focus 9: What does the marker look like after XOR?
print("\n" + "="*80)
print("FOCUS 9: Marker '23 4b 04 de 8a c7 eb 38' after various XORs")
print("="*80)
marker_bytes = bytes.fromhex('234b04de8ac7eb38')
for xor_val in range(256):
    decoded = bytes(b ^ xor_val for b in marker_bytes)
    printable = sum(1 for b in decoded if 32 <= b < 127)
    if printable >= 6:
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in decoded)
        print(f"  XOR 0x{xor_val:02x}: {decoded.hex()} = '{ascii_str}'")

# Try XOR with null pattern
decoded_marker = bytes(marker_bytes[j] ^ key[j % 8] for j in range(8))
ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in decoded_marker)
print(f"  XOR null_key: {decoded_marker.hex()} = '{ascii_str}'")

# Focus 10: Identify the 5 distinct 8-byte values that appear in the data
print("\n" + "="*80)
print("FOCUS 10: The 5 (or more) distinct 8-byte non-null data values")
print("="*80)
null_pat = bytes.fromhex('00f736f388946906')

# Collect all 8-byte values that appear more than once and are not null
eight_byte_counts = Counter()
for i in range(0, len(data) - 7, 8):
    chunk = data[i:i+8]
    if chunk != null_pat and chunk != b'\x00' * 8:
        eight_byte_counts[chunk] += 1

print(f"  Non-null, non-zero 8-byte values (sorted by frequency):")
for val, count in eight_byte_counts.most_common(30):
    hex_str = val.hex()
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in val)
    print(f"    {hex_str} ('{ascii_str}') x{count}")

# Focus 11: The "other" null-like patterns
print("\n" + "="*80)
print("FOCUS 11: Other frequent 8-byte patterns (potential secondary null/zero values)")
print("="*80)
all_eight = Counter()
for i in range(0, len(data) - 7, 1):
    chunk = data[i:i+8]
    all_eight[chunk] += 1

print("  Top 20 most frequent 8-byte patterns overall:")
for val, count in all_eight.most_common(20):
    hex_str = val.hex()
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in val)
    print(f"    {hex_str} ('{ascii_str}') x{count}")

# Focus 12: Try to interpret the data fields as IEEE 754 doubles or floats
print("\n" + "="*80)
print("FOCUS 12: Data field interpretation (records 100+, bytes 8-15 and 16-23)")
print("="*80)
for i in range(100, 110):
    off = i * 64
    field1 = data[off+8:off+16]
    field2 = data[off+16:off+24]
    field3 = data[off+24:off+32]

    # Try as double
    try:
        d1 = struct.unpack('<d', field1)[0]
    except:
        d1 = None
    try:
        d2 = struct.unpack('<d', field2)[0]
    except:
        d2 = None

    # Try as two floats
    try:
        f1a, f1b = struct.unpack('<ff', field1)
    except:
        f1a = f1b = None

    # Try as uint32
    u1, u2 = struct.unpack('<II', field1)

    print(f"  rec{i}: field1={field1.hex()} u32=[{u1},{u2}] f32=[{f1a:.4e},{f1b:.4e}] d64={d1:.4e}")
    print(f"         field2={field2.hex()}  (likely null/zero pattern)")
    print(f"         field3={field3.hex()}  u32={struct.unpack('<II', field3)}")

# Focus 13: Look for record counts or directory-like structures
print("\n" + "="*80)
print("FOCUS 13: Header bytes 0x00-0x0F interpreted as record count/directory")
print("="*80)
header = data[:16]
print(f"  Header bytes: {header.hex()}")
val32_0 = struct.unpack('<I', header[:4])[0]
val32_1 = struct.unpack('<I', header[4:8])[0]
val32_2 = struct.unpack('<I', header[8:12])[0]
val32_3 = struct.unpack('<I', header[12:16])[0]
print(f"  As 4 x uint32: {val32_0}, {val32_1}, {val32_2}, {val32_3}")
print(f"  As 4 x uint32 (hex): 0x{val32_0:08x}, 0x{val32_1:08x}, 0x{val32_2:08x}, 0x{val32_3:08x}")
print(f"  val32_0 / 64 = {val32_0 / 64:.2f}")
print(f"  val32_0 mod 64 = {val32_0 % 64}")

# Try to interpret as a checksum/hash
print(f"\n  First 8 bytes could be a file signature/hash:")
print(f"    {header[:8].hex()}")
print(f"    As uint64: {struct.unpack('<Q', header[:8])[0]}")
print(f"    As uint64 BE: {struct.unpack('>Q', header[:8])[0]}")

# Focus 14: Count records per type (marker, null, data, zeros)
print("\n" + "="*80)
print("FOCUS 14: Record type classification")
print("="*80)
marker_pat = bytes.fromhex('234b04de8ac7eb38')
zero_pat = b'\x00' * 8

n_marker = 0
n_null = 0
n_zero = 0
n_mixed = 0

for i in range(len(data) // 64):
    off = i * 64
    chunk = data[off:off+64]
    first8 = chunk[:8]
    if first8 == marker_pat:
        n_marker += 1
    elif first8 == null_pat:
        n_null += 1
    elif first8 == zero_pat:
        n_zero += 1
    else:
        n_mixed += 1

print(f"  Records starting with marker (234b04de8ac7eb38): {n_marker}")
print(f"  Records starting with null pattern (00f736f388946906): {n_null}")
print(f"  Records starting with zeros (0000000000000000): {n_zero}")
print(f"  Records with other first 8 bytes: {n_mixed}")
print(f"  Total: {n_marker + n_null + n_zero + n_mixed}")

# Focus 15: Scan for "record start" markers - bytes[16:24] of marker records
print("\n" + "="*80)
print("FOCUS 15: Bytes[16:23] distribution in marker-starting records")
print("="*80)
val16_counts = Counter()
for i in range(len(data) // 64):
    off = i * 64
    if data[off:off+8] == marker_pat:
        val16 = data[off+16:off+24]
        val16_counts[val16] += 1

print(f"  Bytes[16:23] values in marker records:")
for val, count in val16_counts.most_common(20):
    hex_str = val.hex()
    print(f"    {hex_str} x{count}")

print("\nDone!")
