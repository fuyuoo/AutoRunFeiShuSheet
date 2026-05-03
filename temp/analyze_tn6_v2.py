#!/usr/bin/env python3
"""
Comprehensive analysis of Tongdaxin (通达信) .tn6 binary formula file - v2
Deeper analysis of the 64-byte repeating structure discovered in v1.
"""
import struct
import math
import sys
import io
from collections import Counter, defaultdict

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

FILE_PATH = r"D:\PythonWorkSpace\AutoRunFeiShuSheet\temp\123.tn6"

TDX_KEYWORDS = [
    b'VAR', b'DRAWTEXT', b'DRAWICON', b'STICKLINE', b'IF', b'MA', b'EMA',
    b'CROSS', b'HHV', b'LLV', b'VOL', b'CLOSE', b'OPEN', b'HIGH', b'LOW',
    b'REF', b'SMA', b'KDJ', b'MACD', b'CCI', b'BOLL', b'RSI', b'SAR', b'OBV',
    b'BIAS', b'DMI', b'WR', b'PSY', b'VR', b'ARBR', b'CR', b'ASI', b'EMV',
    b'WVAD', b'MIKE', b'DRAWNULL', b'COLOR', b'LINETHICK', b'POINTDOT',
    b'CIRCLEDOT', b'DOTLINE', b'SOLIDLINE', b'NODRAW', b'STICK', b'VOLSTICK',
    b'COLORSTICK', b'LINESTICK', b'PLOYLINE', b'DRAWLINE', b'DRAWKLINE',
    b'DRAWGBK', b'ALIGN', b'VALIGN', b'STICK3D', b'BAND', b'FILLRGN',
    b'DRAWNUMBER', b'PARTLINE', b'DRAWBAND', b'NOTEXT',
    b'COEF', b'CONSTANT', b'FILTER', b'COUNT', b'SUM', b'ABS', b'MAX', b'MIN',
    b'POW', b'SQRT', b'LN', b'LOG', b'EXP', b'SIGN', b'CEILING', b'FLOOR',
    b'ROUND', b'INTPART', b'MOD', b'BETWEEN', b'RANGE', b'BARSNEXT',
    b'BARSLAST', b'BARSCOUNT', b'BARSSINCE', b'DATE', b'TIME', b'YEAR',
    b'MONTH', b'WEEK', b'DAY', b'HOUR', b'MINUTE', b'TOTALCAPITAL',
    b'CAPITAL', b'AMOUNT', b'ADVANCE', b'DECLINE', b'SETCODE', b'SELF',
    b'EX2', b'ALIGN0', b'XMA', b'DMA', b'TMA', b'MEMA', b'WMA', b'T3',
]

def entropy(data):
    if not data:
        return 0
    counter = Counter(data)
    length = len(data)
    return -sum((c/length) * math.log2(c/length) for c in counter.values())

def hexdump(data, start=0, length=256, width=16):
    for i in range(0, min(length, len(data) - start), width):
        chunk = data[start+i:start+i+width]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"  {start+i:08x}  {hex_part:<{width*3}}  {ascii_part}")

def main():
    with open(FILE_PATH, 'rb') as f:
        data = f.read()

    print("=" * 90)
    print("  TONGDAXIN .tn6 BINARY FILE ANALYSIS v2")
    print(f"  File: {FILE_PATH}")
    print(f"  Size: {len(data)} bytes (0x{len(data):x})")
    print("=" * 90)

    # ========================================================================
    # 1. HEADER ANALYSIS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  1. HEADER ANALYSIS")
    print("=" * 90)

    print("\n  First 256 bytes hex dump:")
    hexdump(data, 0, 256)

    print("\n  First 16 bytes as little-endian u32:")
    for i in range(0, min(64, len(data)), 4):
        val = struct.unpack_from('<I', data, i)[0]
        print(f"    offset 0x{i:02x}: 0x{val:08x} ({val})")

    # Check for magic signatures
    print(f"\n  First 4 bytes: {data[:4].hex()}")
    print(f"  Bytes 0x10-0x18: {data[0x10:0x18].hex()}")
    print(f"  Bytes 0x20-0x28: {data[0x20:0x28].hex()}")

    # ========================================================================
    # 2. NULL PLACEHOLDER PATTERN ANALYSIS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  2. NULL PLACEHOLDER PATTERN ANALYSIS")
    print("=" * 90)

    # The null pattern is 00 f7 36 f3 88 94 69 06 (9 bytes with leading 00)
    # or f7 36 f3 88 94 69 06 99 (8 bytes without)
    # From v1 output, the repeating unit is: 00 f7 36 f3 88 94 69 06

    null8 = bytes.fromhex('00f736f388946906')  # 8 bytes
    null9 = bytes.fromhex('00f736f38894690699')  # 9 bytes
    null8b = bytes.fromhex('f736f38894690699')  # without leading 00

    for label, pat in [("00f736f388946906 (8 bytes)", null8),
                        ("00f736f38894690699 (9 bytes)", null9),
                        ("f736f38894690699 (8 bytes, no leading 00)", null8b)]:
        count = data.count(pat)
        print(f"\n  Pattern {label}: {count} occurrences")
        if count > 0 and count <= 20:
            pos = 0
            while True:
                pos = data.find(pat, pos)
                if pos == -1:
                    break
                ctx_before = data[max(0,pos-8):pos].hex()
                ctx_after = data[pos+len(pat):pos+len(pat)+8].hex()
                print(f"    at 0x{pos:04x}: [{ctx_before}] [{pat.hex()}] [{ctx_after}]")
                pos += 1

    # Check if the null pattern aligns with the 64-byte structure
    print(f"\n  Checking null-pattern alignment with 64-byte boundary:")
    pos = 0
    null_positions = []
    while True:
        pos = data.find(null8, pos)
        if pos == -1:
            break
        null_positions.append(pos)
        mod64 = pos % 64
        print(f"    0x{pos:04x} (mod 64 = {mod64})")
        pos += 1

    # ========================================================================
    # 3. 64-BYTE REPEATING STRUCTURE ANALYSIS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  3. 64-BYTE REPEATING STRUCTURE ANALYSIS")
    print("=" * 90)

    file_size = len(data)
    num_records = file_size // 64
    remainder = file_size % 64
    print(f"\n  File size: {file_size} bytes")
    print(f"  64-byte records: {num_records} (with {remainder} bytes remainder)")

    # The marker 2c234b04de8ac7eb38 appears at regular 64-byte intervals
    # Let's verify this
    marker = bytes.fromhex('39042c23')
    pos = 0
    marker_positions = []
    while True:
        pos = data.find(marker, pos)
        if pos == -1:
            break
        marker_positions.append(pos)
        pos += 1

    print(f"\n  Marker '39042c23' found {len(marker_positions)} times")
    if marker_positions:
        print(f"  First few positions: {[f'0x{p:04x}' for p in marker_positions[:10]]}")
        if len(marker_positions) > 1:
            gaps = [marker_positions[i+1] - marker_positions[i] for i in range(min(10, len(marker_positions)-1))]
            print(f"  Gaps between first occurrences: {gaps}")

    # Print the first several 64-byte records for comparison
    print(f"\n  First 10 64-byte records:")
    for rec_idx in range(min(10, num_records)):
        offset = rec_idx * 64
        chunk = data[offset:offset+64]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"    Record {rec_idx:3d} (0x{offset:04x}): {hex_str}")
        print(f"                                    {ascii_str}")

    # Analyze which byte positions within the 64-byte record are constant vs variable
    print(f"\n  Per-position analysis across all {num_records} records:")
    print(f"  (Showing byte positions that vary vs remain constant)")

    # Check each byte position across all records
    for pos_in_record in range(64):
        values = set()
        for rec_idx in range(num_records):
            offset = rec_idx * 64 + pos_in_record
            if offset < file_size:
                values.add(data[offset])
        if len(values) == 1:
            print(f"    Byte[{pos_in_record:2d}]: CONSTANT = 0x{list(values)[0]:02x}")
        elif len(values) <= 5:
            val_counts = Counter(data[rec_idx * 64 + pos_in_record]
                                for rec_idx in range(num_records)
                                if rec_idx * 64 + pos_in_record < file_size)
            val_str = ', '.join(f'0x{v:02x}({c})' for v, c in val_counts.most_common())
            print(f"    Byte[{pos_in_record:2d}]: FEW VALUES = {val_str}")
        # else: many values, skip for brevity

    # Print records 0, 50, 100, 200, 400, 600 for comparison
    print(f"\n  Comparison of selected records (to see variation):")
    for rec_idx in [0, 1, 2, 3, 4, 50, 100, 200, 400, 600]:
        if rec_idx >= num_records:
            continue
        offset = rec_idx * 64
        chunk = data[offset:offset+64]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        print(f"    Record {rec_idx:3d} (0x{offset:04x}): {hex_str}")

    # ========================================================================
    # 4. DETAILED RECORD STRUCTURE
    # ========================================================================
    print("\n" + "=" * 90)
    print("  4. DETAILED RECORD STRUCTURE (per-byte value distribution)")
    print("=" * 90)

    for pos_in_record in range(64):
        val_counts = Counter()
        for rec_idx in range(num_records):
            offset = rec_idx * 64 + pos_in_record
            if offset < file_size:
                val_counts[data[offset]] += 1

        unique = len(val_counts)
        top_vals = val_counts.most_common(5)
        top_str = ', '.join(f'0x{v:02x}({c})' for v, c in top_vals)

        if unique <= 10:
            all_vals = sorted(val_counts.keys())
            all_str = ', '.join(f'0x{v:02x}' for v in all_vals)
            print(f"  byte[{pos_in_record:2d}]: {unique:3d} unique values: {all_str}")
        else:
            top3 = val_counts.most_common(3)
            top3_str = ', '.join(f'0x{v:02x}({c})' for v, c in top3)
            print(f"  byte[{pos_in_record:2d}]: {unique:3d} unique values, top3: {top3_str}")

    # ========================================================================
    # 5. ENTROPY ANALYSIS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  5. ENTROPY ANALYSIS")
    print("=" * 90)

    print(f"\n  Overall file entropy: {entropy(data):.4f} / 8.0")

    # Per-record entropy
    print(f"\n  Per-record entropy (first 20 records):")
    for rec_idx in range(min(20, num_records)):
        offset = rec_idx * 64
        chunk = data[offset:offset+64]
        e = entropy(chunk)
        bar = '#' * int(e * 5)
        print(f"    Record {rec_idx:3d}: {e:.4f} {bar}")

    # Byte position entropy (across all records)
    print(f"\n  Per-position entropy within 64-byte record structure:")
    for pos_in_record in range(64):
        values = [data[rec_idx * 64 + pos_in_record]
                  for rec_idx in range(num_records)
                  if rec_idx * 64 + pos_in_record < file_size]
        e = entropy(values)
        unique = len(set(values))
        bar = '#' * int(e * 5)
        print(f"    byte[{pos_in_record:2d}]: entropy={e:.4f}, unique={unique:3d} {bar}")

    # ========================================================================
    # 6. BYTE FREQUENCY ANALYSIS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  6. BYTE FREQUENCY ANALYSIS")
    print("=" * 90)

    counter = Counter(data)
    total = len(data)
    expected = total / 256
    chi_sq = sum((counter.get(i, 0) - expected)**2 / expected for i in range(256))

    print(f"\n  Top 30 most frequent bytes:")
    for byte_val, count in counter.most_common(30):
        pct = count / total * 100
        print(f"    0x{byte_val:02x}: {count:6d} ({pct:5.2f}%)")

    print(f"\n  Chi-squared: {chi_sq:.2f}")
    print(f"  {'Uniform (encrypted?)' if chi_sq < 300 else 'Skewed (structured data)'}")

    missing = [i for i in range(256) if counter.get(i, 0) == 0]
    if missing:
        print(f"\n  Never-appearing bytes ({len(missing)}): {', '.join(f'0x{b:02x}' for b in missing)}")

    # ========================================================================
    # 7. STRING EXTRACTION (GBK focus)
    # ========================================================================
    print("\n" + "=" * 90)
    print("  7. STRING EXTRACTION (GBK/GB18030)")
    print("=" * 90)

    # Scan for GBK strings
    gbk_strings = []
    i = 0
    while i < len(data) - 1:
        b = data[i]
        if 0x81 <= b <= 0xFE:
            b2 = data[i+1]
            if 0x40 <= b2 <= 0xFE and b2 != 0x7F:
                try:
                    char = bytes([b, b2]).decode('gbk')
                    if 0x4e00 <= ord(char) <= 0x9fff:
                        # CJK char found, extend
                        chars = [char]
                        pos = i + 2
                        while pos < len(data) - 1:
                            nb = data[pos]
                            if 0x81 <= nb <= 0xFE:
                                nb2 = data[pos+1]
                                if 0x40 <= nb2 <= 0xFE and nb2 != 0x7F:
                                    try:
                                        nchar = bytes([nb, nb2]).decode('gbk')
                                        chars.append(nchar)
                                        pos += 2
                                    except:
                                        break
                                else:
                                    break
                            elif 32 <= nb < 127:
                                chars.append(chr(nb))
                                pos += 1
                            elif nb == 0:
                                break
                            else:
                                break
                        text = ''.join(chars)
                        if len(text) >= 1:
                            gbk_strings.append((i, text))
                        i = pos
                        continue
                except:
                    pass
        elif 32 <= b < 127:
            end = i
            while end < len(data) and 32 <= data[end] < 127:
                end += 1
            if end - i >= 4:
                text = data[i:end].decode('ascii')
                gbk_strings.append((i, text))
                i = end
                continue
        i += 1

    # Deduplicate
    seen = set()
    unique_strings = []
    for offset, text in gbk_strings:
        if text not in seen:
            seen.add(text)
            unique_strings.append((offset, text))

    unique_strings.sort(key=lambda x: x[0])
    print(f"\n  Found {len(unique_strings)} unique strings (GBK+ASCII, len>=1 CJK or len>=4 ASCII):")
    for offset, text in unique_strings[:200]:
        has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in text)
        marker = "[CJK]" if has_cjk else "[ASCII]"
        rec_idx = offset // 64
        pos_in_rec = offset % 64
        print(f"    0x{offset:04x} [rec{rec_idx:3d}+{pos_in_rec:2d}] {marker}: '{text}'")

    # ========================================================================
    # 8. DEEP STRING SCAN - Try reading strings from within records
    # ========================================================================
    print("\n" + "=" * 90)
    print("  8. RECORD-LEVEL STRING SCAN")
    print("=" * 90)

    # Check each 64-byte record for embedded strings
    print(f"\n  Scanning each 64-byte record for GBK/ASCII strings...")
    for rec_idx in range(min(20, num_records)):
        offset = rec_idx * 64
        chunk = data[offset:offset+64]

        # Try GBK decode of the whole record (skip nulls)
        try:
            # Replace null bytes with spaces for decode attempt
            cleaned = bytes(b if b != 0 else 0x20 for b in chunk)
            text = cleaned.decode('gbk', errors='ignore')
            # Filter printable
            text = ''.join(c if (32 <= ord(c) < 127) or (0x4e00 <= ord(c) <= 0x9fff) else '.' for c in text)
            if any(0x4e00 <= ord(c) <= 0x9fff for c in text):
                print(f"    Record {rec_idx} (0x{offset:04x}): GBK=> '{text}'")
        except:
            pass

        # Try ASCII
        ascii_text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        if any(c != '.' for c in ascii_text):
            print(f"    Record {rec_idx} (0x{offset:04x}): ASCII=> '{ascii_text}'")

    # ========================================================================
    # 9. KEYWORD SEARCH (TDX formulas)
    # ========================================================================
    print("\n" + "=" * 90)
    print("  9. TDX KEYWORD SEARCH")
    print("=" * 90)

    print(f"\n  Raw data keyword search:")
    found_any = False
    for kw in TDX_KEYWORDS:
        pos = 0
        positions = []
        while True:
            pos = data.find(kw, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 1
        if positions:
            found_any = True
            kw_str = kw.decode('ascii', errors='replace')
            pos_str = ', '.join(f'0x{p:x}' for p in positions[:10])
            print(f"    '{kw_str}': {len(positions)} hits at {pos_str}")
    if not found_any:
        print("    No TDX keywords found in raw data.")

    # XOR decode attempts
    print(f"\n  XOR decode + keyword search:")
    for xor_key in range(256):
        decoded = bytes(b ^ xor_key for b in data)
        matches = [kw.decode('ascii') for kw in TDX_KEYWORDS if kw in decoded]
        if len(matches) >= 3:  # Only report if multiple keywords match
            print(f"    XOR 0x{xor_key:02x}: {len(matches)} keywords: {', '.join(matches[:10])}")

    # Multi-byte XOR
    print(f"\n  Multi-byte XOR + keyword search:")
    for key_bytes in [
        b'\x00', b'\x42', b'\x73', b'\x37', b'\x13', b'\x88',
        b'\x00\x42', b'\x42\x73', b'\x37\x13', b'\x13\x88',
        b'\x00\x42\x73', b'\x42\x73\x37', b'\x37\x13\x88',
        b'\x00\x42\x73\x37', b'\x42\x73\x37\x13', b'\x37\x13\x88\x00',
        b'\x73\x37\x13\x88',
    ]:
        decoded = bytes(data[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(data)))
        matches = [kw.decode('ascii') for kw in TDX_KEYWORDS if kw in decoded]
        if len(matches) >= 3:
            print(f"    XOR {key_bytes.hex()}: {len(matches)} keywords: {', '.join(matches[:10])}")

    # ========================================================================
    # 10. XOR DECODE - Check if specific bytes are XOR-encoded
    # ========================================================================
    print("\n" + "=" * 90)
    print("  10. SELECTIVE XOR ANALYSIS")
    print("=" * 90)

    # The null placeholder 00f736f388946906 might be XOR(0000000000000000, key)
    # Or it might be XOR(some_known_value, key)
    # Let's check if XORing the first 8 bytes with common patterns gives us something

    print(f"\n  Testing if null pattern 00f736f388946906 is XOR of zeros with a key:")
    null_pat = bytes.fromhex('00f736f388946906')
    print(f"    If null_pattern = XOR(0000000000000000, key) => key = {null_pat.hex()}")

    # Try XORing entire file with null pattern to see if we get meaningful text
    print(f"\n  XOR entire file with 8-byte null pattern repeating:")
    decoded = bytes(data[i] ^ null_pat[i % 8] for i in range(len(data)))
    # Count printable
    printable = sum(1 for b in decoded if 32 <= b < 127)
    pct = printable / len(decoded) * 100
    print(f"    Printable ASCII: {printable}/{len(decoded)} ({pct:.1f}%)")

    # Check for keywords
    matches = [kw.decode('ascii') for kw in TDX_KEYWORDS if kw in decoded]
    print(f"    TDX keywords found: {len(matches)} - {', '.join(matches[:20])}")

    # Show first 256 bytes of decoded
    print(f"\n    First 256 bytes after XOR with null pattern:")
    hexdump(decoded, 0, 256)

    # Try extracting strings from XOR-decoded data
    print(f"\n    ASCII strings in XOR-decoded data:")
    i = 0
    found_strings = []
    while i < len(decoded):
        if 32 <= decoded[i] < 127:
            end = i
            while end < len(decoded) and 32 <= decoded[end] < 127:
                end += 1
            if end - i >= 3:
                found_strings.append((i, decoded[i:end].decode('ascii', errors='replace')))
            i = end
        else:
            i += 1
    for offset, text in found_strings[:50]:
        print(f"      0x{offset:04x}: '{text}'")

    # Also try GBK on XOR-decoded data
    print(f"\n    GBK strings in XOR-decoded data:")
    i = 0
    gbk_found = []
    while i < len(decoded) - 1:
        b = decoded[i]
        if 0x81 <= b <= 0xFE:
            b2 = decoded[i+1]
            if 0x40 <= b2 <= 0xFE and b2 != 0x7F:
                try:
                    char = bytes([b, b2]).decode('gbk')
                    if 0x4e00 <= ord(char) <= 0x9fff:
                        chars = [char]
                        pos = i + 2
                        while pos < len(decoded) - 1:
                            nb = decoded[pos]
                            if 0x81 <= nb <= 0xFE:
                                nb2 = decoded[pos+1]
                                if 0x40 <= nb2 <= 0xFE and nb2 != 0x7F:
                                    try:
                                        nchar = bytes([nb, nb2]).decode('gbk')
                                        chars.append(nchar)
                                        pos += 2
                                    except:
                                        break
                                else:
                                    break
                            elif 32 <= decoded[pos] < 127:
                                chars.append(chr(decoded[pos]))
                                pos += 1
                            else:
                                break
                        text = ''.join(chars)
                        if len(text) >= 1:
                            gbk_found.append((i, text))
                        i = pos
                        continue
                except:
                    pass
        i += 1

    for offset, text in gbk_found[:50]:
        print(f"      0x{offset:04x}: '{text}'")

    # ========================================================================
    # 11. MIXED STRUCTURE ANALYSIS - header + records
    # ========================================================================
    print("\n" + "=" * 90)
    print("  11. MIXED STRUCTURE: Header + Records")
    print("=" * 90)

    # The file is 44752 bytes. Let's check various record sizes
    for record_size in [16, 32, 48, 64, 80, 96, 128, 256]:
        num = len(data) // record_size
        rem = len(data) % record_size
        # Calculate entropy of each chunk
        entropies = [entropy(data[i*record_size:(i+1)*record_size]) for i in range(min(num, 10))]
        avg_e = sum(entropies) / len(entropies) if entropies else 0
        print(f"  Record size {record_size:3d}: {num:5d} records, {rem:4d} remainder, avg entropy (first 10): {avg_e:.4f}")

    # Focus on 64-byte records: what's at offset 0x00 vs later records?
    print(f"\n  First record (0x00-0x3F) is likely the FILE HEADER:")
    hexdump(data, 0, 64)

    print(f"\n  Records seem to start at offset 0x40 (64):")
    for i in range(5):
        offset = 0x40 + i * 64
        chunk = data[offset:offset+64]
        hex_str = ' '.join(f'{b:02x}' for b in chunk)
        print(f"    rec{i} (0x{offset:04x}): {hex_str}")

    # Check if maybe records are NOT 64 bytes but contain 64-byte sub-blocks
    # Let's look at the marker 2c234b04de8ac7eb38 more carefully
    print(f"\n  Detailed analysis of marker '042c234b04de8ac7eb38':")
    marker39 = bytes.fromhex('39042c234b04de8ac7eb38')
    count = data.count(marker39)
    print(f"  Pattern '39042c234b04de8ac7eb38': {count} occurrences")
    if count > 0:
        pos = 0
        while True:
            pos = data.find(marker39, pos)
            if pos == -1:
                break
            print(f"    at 0x{pos:04x}, record={pos//64}, offset_in_record={pos%64}")
            pos += 1

    # What is this marker value interpreted as?
    val32 = struct.unpack('<I', bytes.fromhex('39042c23'))[0]
    val32s = struct.unpack('<i', bytes.fromhex('39042c23'))[0]
    fval = struct.unpack('<f', bytes.fromhex('39042c23'))[0]
    print(f"\n  Marker '39042c23' as LE u32: {val32} (0x{val32:08x})")
    print(f"  Marker '39042c23' as LE i32: {val32s}")
    print(f"  Marker '39042c23' as LE f32: {fval}")

    # ========================================================================
    # 12. HEX DUMP OF ENTIRE FILE IN 64-BYTE ROWS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  12. FULL FILE HEX DUMP (64-byte rows)")
    print("=" * 90)

    for i in range(0, len(data), 64):
        chunk = data[i:i+64]
        hex_str = ' '.join(f'{b:02x}' for b in chunk[:32])
        hex_str2 = ' '.join(f'{b:02x}' for b in chunk[32:])
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        rec_num = i // 64
        print(f"  rec{rec_num:4d} 0x{i:04x}: {hex_str:<96s}|{hex_str2:<96s}| {ascii_str}")

    # ========================================================================
    # 13. POTENTIAL FORMULA STRUCTURE DETECTION
    # ========================================================================
    print("\n" + "=" * 90)
    print("  13. FORMULA STRUCTURE DETECTION")
    print("=" * 90)

    # In TDX .tn6 files, each formula might have:
    # - Formula name (Chinese)
    # - Formula description
    # - Formula source code
    # - Parameters
    # - Compiled bytecode

    # Look for potential formula boundaries by checking where the null pattern
    # is NOT present (i.e., where real data lives)

    print(f"\n  Records without null pattern (containing actual data):")
    null_pat_8 = bytes.fromhex('00f736f388946906')
    for rec_idx in range(num_records):
        offset = rec_idx * 64
        chunk = data[offset:offset+64]
        null_count = chunk.count(null_pat_8)
        if null_count < 7:  # Not mostly null pattern
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"    rec{rec_idx:4d} 0x{offset:04x} (null_count={null_count}): {hex_str}")
            print(f"                                            {ascii_str}")

    # ========================================================================
    # 14. CHECK IF DATA IS ENCODED WITH BYTE-SUBSTITUTION CIPHER
    # ========================================================================
    print("\n" + "=" * 90)
    print("  14. BYTE-SUBSTITUTION CIPHER CHECK")
    print("=" * 90)

    # If the data is encoded with a substitution cipher (like some TDX formats),
    # then byte frequency should still be skewed (not uniform)
    # but no ASCII/GBK text should be directly readable

    # Check: do any bytes in the range 0x81-0xFE (GBK first byte) pair with
    # valid GBK second bytes (0x40-0xFE)?
    gbk_pair_count = 0
    total_pairs = 0
    for i in range(len(data) - 1):
        b1, b2 = data[i], data[i+1]
        total_pairs += 1
        if 0x81 <= b1 <= 0xFE and 0x40 <= b2 <= 0xFE and b2 != 0x7F:
            gbk_pair_count += 1

    print(f"\n  Valid GBK byte pairs: {gbk_pair_count}/{total_pairs} ({gbk_pair_count/total_pairs*100:.2f}%)")
    if gbk_pair_count / total_pairs > 0.1:
        print(f"  => High rate of valid GBK pairs suggests data is NOT heavily encoded")
    else:
        print(f"  => Low rate of valid GBK pairs suggests data may be encoded/encrypted")

    # Try byte substitution: XOR with single byte
    # If we assume the null pattern 00f736f388946906 maps to 0000000000000000,
    # then key = 00f736f388946906 (repeating 8-byte key)
    print(f"\n  Using null pattern as XOR key (assuming null_pattern = XOR(zeros, key)):")
    key = bytes.fromhex('00f736f388946906')
    decoded = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))

    # Check for GBK strings in decoded data
    print(f"  Checking for GBK strings in XOR-decoded data...")
    gbk_decoded = []
    i = 0
    while i < len(decoded) - 1:
        b = decoded[i]
        if 0x81 <= b <= 0xFE:
            b2 = decoded[i+1]
            if 0x40 <= b2 <= 0xFE and b2 != 0x7F:
                try:
                    char = bytes([b, b2]).decode('gbk')
                    if 0x4e00 <= ord(char) <= 0x9fff:
                        chars = [char]
                        pos = i + 2
                        while pos < len(decoded) - 1:
                            nb = decoded[pos]
                            if 0x81 <= nb <= 0xFE:
                                nb2 = decoded[pos+1]
                                if 0x40 <= nb2 <= 0xFE and nb2 != 0x7F:
                                    try:
                                        nchar = bytes([nb, nb2]).decode('gbk')
                                        chars.append(nchar)
                                        pos += 2
                                    except:
                                        break
                                else:
                                    break
                            elif 32 <= decoded[pos] < 127:
                                chars.append(chr(decoded[pos]))
                                pos += 1
                            else:
                                break
                        text = ''.join(chars)
                        if len(text) >= 1:
                            gbk_decoded.append((i, text))
                        i = pos
                        continue
                except:
                    pass
        elif 32 <= b < 127:
            end = i
            while end < len(decoded) and 32 <= decoded[end] < 127:
                end += 1
            if end - i >= 4:
                gbk_decoded.append((i, decoded[i:end].decode('ascii', errors='replace')))
            i = end
            continue
        i += 1

    seen = set()
    for offset, text in gbk_decoded:
        if text not in seen:
            seen.add(text)
            has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in text)
            marker = "[CJK]" if has_cjk else "[ASCII]"
            print(f"    0x{offset:04x} {marker}: '{text}'")

    # ========================================================================
    # 15. ANALYZE THE HEADER RECORD (record 0) IN DETAIL
    # ========================================================================
    print("\n" + "=" * 90)
    print("  15. HEADER RECORD DETAILED ANALYSIS")
    print("=" * 90)

    header = data[0:64]
    print(f"\n  Header bytes:")
    hexdump(header, 0, 64)

    print(f"\n  Possible interpretations of header fields:")
    # Magic (4 bytes)
    magic = header[:4]
    print(f"  [0x00-0x03] Magic: {magic.hex()} = int32={struct.unpack('<i', magic)[0]}")

    # Various 4-byte fields
    for offset, label in [(4, "field1"), (8, "field2"), (12, "field3"),
                           (16, "field4"), (20, "field5"), (24, "field6"),
                           (28, "field7"), (32, "field8"), (36, "field9"),
                           (40, "field10"), (44, "field11"), (48, "field12"),
                           (52, "field13"), (56, "field14"), (60, "field15")]:
        if offset + 4 <= 64:
            val = struct.unpack_from('<I', header, offset)[0]
            vals = struct.unpack_from('<i', header, offset)[0]
            print(f"  [0x{offset:02x}-0x{offset+3:02x}] {label}: u32=0x{val:08x} ({val}) i32={vals}")

    # ========================================================================
    # 16. SCAN FOR KNOWN TDX PATTERNS
    # ========================================================================
    print("\n" + "=" * 90)
    print("  16. KNOWN TDX BINARY PATTERNS")
    print("=" * 90)

    # TDX .tn6 files are compiled formula files. Known patterns:
    # - They may start with a magic number
    # - Formula names are often stored as Pascal strings (length byte + string)
    # - The formula source code may be stored or just the compiled bytecode

    # Look for potential formula count in header
    for offset in [0, 2, 4, 6, 8, 10, 12, 14]:
        if offset + 2 <= len(header):
            val16 = struct.unpack_from('<H', header, offset)[0]
            if 1 <= val16 <= 1000:
                print(f"  Potential formula count at offset {offset}: u16={val16}")

    # Try to find the data section start
    # In many binary formats, there's a pointer/offset to where data begins
    for offset in range(0, min(32, len(header)), 4):
        val = struct.unpack_from('<I', header, offset)[0]
        if 64 <= val <= len(data):
            print(f"  Potential data offset at header[0x{offset:02x}]: {val} (0x{val:x})")

    print(f"\n  Analysis complete!")

if __name__ == '__main__':
    main()
