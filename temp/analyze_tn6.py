#!/usr/bin/env python3
"""
Deep analysis of Tongdaxin .tn6 file - XOR decoded metadata region.
Focus: records 0-36 for formula names, source code, parameters.
"""
import struct
import re
from collections import Counter

XOR_KEY = bytes([0x00, 0xf7, 0x36, 0xf3, 0x88, 0x94, 0x69, 0x06])
REC_SIZE = 64
INPUT = r"D:\PythonWorkSpace\AutoRunFeiShuSheet\temp\123.tn6"
DECODED = r"D:\PythonWorkSpace\AutoRunFeiShuSheet\temp\123_decoded.bin"

ENCODINGS = ['gbk', 'gb18030', 'gb2312', 'utf-8', 'big5']

TDX_KW = [
    'MA','EMA','SMA','DMA','REF','HHV','LLV','SUM','COUNT','CROSS','IF',
    'AND','OR','NOT','ABS','MAX','MIN','STD','DRAWTEXT','DRAWLINE',
    'DRAWKLINE','STICKLINE','DRAWICON','VOL','CLOSE','OPEN','HIGH','LOW',
    'AMOUNT','KDJ','MACD','RSI','BOLL','CCI','BIAS','OBV','BUY','SELL',
    'ENTERLONG','EXITLONG','WINNER','COST','CAPITAL','DYNAINFO','FINANCE',
    'BARSLAST','BARSCOUNT','FILTER','WMA','EXPMEMA','MEMA','DRAWNULL',
    'NODRAW','COLORRED','COLORGREEN','LINETHICK','POINTDOT','CIRCLEDOT',
    'PARTLINE','DRAWBAND','DRAWNUMBER','FILLRGN','PLOYLINE','DRAWLINE',
    'VOLSTICK','COLORSTICK','LINESTICK','COEF','VAR','SAR','DMI','WR',
    'PSY','VR','CR','ASI','EMV','WVAD','MIKE','XMA','TMA','T3',
    'ALIGN','VALIGN','SETCODE','SELF','DATE','TIME','YEAR','MONTH','WEEK',
    'DAY','HOUR','MINUTE','TOTALCAPITAL','AMOUNT','ADVANCE','DECLINE',
    'ROUND','FLOOR','CEILING','SQRT','LN','LOG','EXP','POW','MOD',
    'BETWEEN','RANGE','BARSNEXT','BARSSINCE','NOTEXT','DOTLINE','SOLIDLINE',
    'STICK3D','BAND','ALIGN0','EX2','INTPART','SIGN',
]


def xor_decode(data):
    return bytes(b ^ XOR_KEY[i % 8] for i, b in enumerate(data))


def hexdump(data, base=0):
    lines = []
    for i in range(0, len(data), 16):
        hx = ' '.join(f'{b:02x}' for b in data[i:i+16])
        asc = ''.join(chr(b) if 0x20 <= b <= 0x7e else '.' for b in data[i:i+16])
        lines.append(f"  {base+i:04X}: {hx:<48s}  {asc}")
    return '\n'.join(lines)


def try_strings(raw):
    """Try decoding raw bytes with multiple encodings."""
    results = []
    for enc in ENCODINGS:
        try:
            s = raw.decode(enc)
            clean = s.strip('\x00')
            if clean and len(clean) >= 1:
                results.append((enc, clean))
        except:
            pass
    return results


def extract_all_strings(data, min_len=3):
    """Extract readable strings from binary, ASCII and GBK."""
    results = []
    # ASCII
    for m in re.finditer(b'[\x20-\x7e]{' + str(min_len).encode() + b',}', data):
        results.append(('ascii', m.start(), m.group().decode('ascii')))
    # GBK Chinese
    i = 0
    while i < len(data) - 1:
        if 0x81 <= data[i] <= 0xfe:
            j = i
            chars = []
            while j < len(data) - 1:
                if data[j] == 0x00 or data[j] < 0x20:
                    break
                if 0x81 <= data[j] <= 0xfe and j+1 < len(data):
                    b2 = data[j+1]
                    if 0x40 <= b2 <= 0xfe and b2 != 0x7f:
                        try:
                            c = bytes([data[j], b2]).decode('gbk')
                            chars.append(c)
                            j += 2
                            continue
                        except:
                            pass
                if 0x20 <= data[j] <= 0x7e:
                    chars.append(chr(data[j]))
                    j += 1
                else:
                    break
            if chars and any('\u4e00' <= c <= '\u9fff' for c in chars):
                text = ''.join(chars)
                results.append(('gbk', i, text))
                i = j
                continue
        i += 1
    return results


def nibble_swap(data):
    return bytes(((b & 0x0f) << 4) | ((b & 0xf0) >> 4) for b in data)


def byte_rol(data, bits):
    return bytes(((b << bits) | (b >> (8 - bits))) & 0xff for b in data)


def reverse_8(data):
    out = bytearray()
    for i in range(0, len(data), 8):
        out.extend(reversed(data[i:i+8]))
    return bytes(out)


def main():
    with open(INPUT, 'rb') as f:
        raw = f.read()

    print(f"File size: {len(raw)} bytes, {len(raw)//REC_SIZE} records\n")

    # Decode
    dec = xor_decode(raw)
    with open(DECODED, 'wb') as f:
        f.write(dec)
    print(f"Saved decoded file: {DECODED}\n")

    meta_end = 37 * REC_SIZE
    meta = dec[:meta_end]

    # ================================================================
    print("=" * 80)
    print("PART 1: RECORD-BY-RECORD HEX DUMP OF RECORDS 0-36")
    print("=" * 80)
    # ================================================================

    for r in range(37):
        s = r * REC_SIZE
        rec = dec[s:s+REC_SIZE]
        nz = sum(1 for b in rec if b != 0)
        print(f"\n--- Record {r} @ 0x{s:04X} ({nz} non-zero bytes) ---")
        print(hexdump(rec, s))

        # Byte-level field interpretations
        # First 8 bytes as various types
        print(f"  [0:4] uint32LE={struct.unpack('<I', rec[0:4])[0]:>11}  "
              f"int32LE={struct.unpack('<i', rec[0:4])[0]:>11}  "
              f"float32={struct.unpack('<f', rec[0:4])[0]:>14.6f}")
        print(f"  [4:8] uint32LE={struct.unpack('<I', rec[4:8])[0]:>11}  "
              f"int32LE={struct.unpack('<i', rec[4:8])[0]:>11}  "
              f"float32={struct.unpack('<f', rec[4:8])[0]:>14.6f}")
        if nz > 0:
            # Show all non-zero bytes as potential fields
            fields = []
            for i in range(0, 64, 4):
                v = struct.unpack_from('<I', rec, i)[0]
                if v != 0:
                    fields.append((i, v))
            if fields:
                parts = '  '.join(f"[{off:02d}]={val}" for off, val in fields)
                print(f"  Non-zero 4-byte fields: {parts}")

        # Try decoding entire record as text
        decs = try_strings(rec)
        for enc, val in decs:
            if val.strip('\x00'):
                print(f"  TEXT [{enc}]: \"{val}\"")

        # Try each 8-byte field
        for j in range(0, 64, 8):
            chunk = rec[j:j+8]
            if any(b != 0 for b in chunk):
                for enc in ENCODINGS:
                    try:
                        s2 = chunk.decode(enc).strip('\x00')
                        if s2:
                            print(f"  8-byte [{j}:{j+8}] [{enc}]: \"{s2}\"")
                    except:
                        pass
                # Also try as double
                d = struct.unpack('<d', chunk)[0]
                if abs(d) > 1e-10 and abs(d) < 1e15:
                    print(f"  8-byte [{j}:{j+8}] float64={d:.6f}")

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 2: LENGTH-PREFIXED STRING SEARCH IN METADATA")
    print("=" * 80)
    # ================================================================

    # 1-byte length prefix
    print("\n--- 1-byte length prefix (len 3-128) ---")
    for i in range(len(meta) - 1):
        ln = meta[i]
        if 3 <= ln <= 128 and i + 1 + ln <= len(meta):
            cand = meta[i+1:i+1+ln]
            for enc in ENCODINGS:
                try:
                    t = cand.decode(enc).strip('\x00')
                    if t.strip():
                        rec = i // REC_SIZE
                        print(f"  0x{i:04X} (rec {rec}): len={ln} [{enc}] \"{t}\"")
                except:
                    pass

    # 2-byte LE length prefix
    print("\n--- 2-byte LE length prefix (len 3-500) ---")
    for i in range(len(meta) - 2):
        ln = struct.unpack('<H', meta[i:i+2])[0]
        if 3 <= ln <= 500 and i + 2 + ln <= len(meta):
            cand = meta[i+2:i+2+ln]
            for enc in ENCODINGS:
                try:
                    t = cand.decode(enc).strip('\x00')
                    if t.strip():
                        rec = i // REC_SIZE
                        print(f"  0x{i:04X} (rec {rec}): len={ln} [{enc}] \"{t}\"")
                except:
                    pass

    # 2-byte BE length prefix
    print("\n--- 2-byte BE length prefix (len 3-500) ---")
    for i in range(len(meta) - 2):
        ln = struct.unpack('>H', meta[i:i+2])[0]
        if 3 <= ln <= 500 and i + 2 + ln <= len(meta):
            cand = meta[i+2:i+2+ln]
            for enc in ENCODINGS:
                try:
                    t = cand.decode(enc).strip('\x00')
                    if t.strip():
                        rec = i // REC_SIZE
                        print(f"  0x{i:04X} (rec {rec}): len={ln} [{enc}] \"{t}\"")
                except:
                    pass

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 3: TDX KEYWORD SEARCH IN METADATA (post-XOR)")
    print("=" * 80)
    # ================================================================

    for kw in TDX_KW:
        kb = kw.encode('ascii')
        pos = meta.find(kb)
        while pos >= 0:
            rec = pos // REC_SIZE
            print(f"  Found '{kw}' at 0x{pos:04X} (rec {rec})")
            # Show context
            ctx_s = max(0, pos - 16)
            ctx_e = min(len(meta), pos + len(kb) + 16)
            print(f"    Context: {' '.join(f'{b:02x}' for b in meta[ctx_s:ctx_e])}")
            pos = meta.find(kb, pos + 1)

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 4: SECOND-LAYER ENCODING TESTS")
    print("=" * 80)
    # ================================================================

    # 4a. Nibble swap
    print("\n--- 4a: Nibble swap ---")
    ns = nibble_swap(meta)
    ns_strings = extract_all_strings(ns, min_len=3)
    for kw in TDX_KW:
        kb = kw.encode('ascii')
        if kb in ns:
            idx = ns.find(kb)
            print(f"  Found '{kw}' at 0x{idx:04X}")
    for stype, off, val in ns_strings[:30]:
        print(f"  0x{off:04X} [{stype}]: \"{val}\"")
    if not ns_strings:
        print("  No readable strings after nibble swap.")

    # 4b. Byte rotation ROL 1-7
    print("\n--- 4b: Byte rotation (ROL) ---")
    for bits in range(1, 8):
        rot = byte_rol(meta, bits)
        rot_strs = extract_all_strings(rot, min_len=3)
        kw_hits = [kw for kw in TDX_KW if kw.encode('ascii') in rot]
        if rot_strs or kw_hits:
            print(f"\n  ROL {bits}:")
            if kw_hits:
                print(f"    Keywords: {kw_hits}")
            for stype, off, val in rot_strs[:15]:
                print(f"    0x{off:04X} [{stype}]: \"{val}\"")

    # 4c. Reverse 8-byte groups
    print("\n--- 4c: Reverse 8-byte groups ---")
    rev = reverse_8(meta)
    rev_strs = extract_all_strings(rev, min_len=3)
    kw_hits = [kw for kw in TDX_KW if kw.encode('ascii') in rev]
    if kw_hits:
        print(f"  Keywords: {kw_hits}")
    for stype, off, val in rev_strs[:15]:
        print(f"  0x{off:04X} [{stype}]: \"{val}\"")
    if not kw_hits and not rev_strs:
        print("  No results.")

    # 4d. Combined: nibble_swap then XOR with shifted key
    print("\n--- 4d: Nibble swap + XOR shift ---")
    ns = nibble_swap(meta)
    for shift in range(8):
        combined = bytes(b ^ XOR_KEY[(i + shift) % 8] for i, b in enumerate(ns))
        kw_hits = [kw for kw in TDX_KW if kw.encode('ascii') in combined]
        combo_strs = extract_all_strings(combined, min_len=3)
        if kw_hits or combo_strs:
            print(f"\n  nibble_swap + XOR(shift={shift}):")
            if kw_hits:
                print(f"    Keywords: {kw_hits}")
            for stype, off, val in combo_strs[:10]:
                print(f"    0x{off:04X} [{stype}]: \"{val}\"")

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 5: ALL READABLE STRINGS IN ENTIRE DECODED FILE")
    print("=" * 80)
    # ================================================================

    all_strs = extract_all_strings(dec, min_len=3)
    seen = set()
    unique = []
    for item in all_strs:
        key = (item[0], item[2])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    unique.sort(key=lambda x: x[1])

    for stype, off, val in unique:
        rec = off // REC_SIZE
        print(f"  0x{off:06X} (rec {rec:>4d}) [{stype:>5s}]: \"{val}\"")

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 6: RECORD STRUCTURE - HEADER FIELD PATTERNS")
    print("=" * 80)
    # ================================================================

    print("\n--- First 8 bytes of each record (potential IDs/counters/offsets) ---")
    for r in range(min(40, len(dec) // REC_SIZE)):
        off = r * REC_SIZE
        b = dec[off:off+8]
        v32a = struct.unpack('<I', b[0:4])[0]
        v32b = struct.unpack('<I', b[4:8])[0]
        v16s = struct.unpack('<h', b[0:2])[0]
        v16m = struct.unpack('<h', b[2:4])[0]
        print(f"  rec {r:>3d} (0x{off:04X}): "
              f"u32=[{v32a:>11},{v32b:>11}]  "
              f"i16=[{v16s:>6},{v16m:>6}]  "
              f"{' '.join(f'{x:02x}' for x in b)}")

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 7: NON-ZERO BYTE MAP")
    print("=" * 80)
    # ================================================================
    print("Each '.' = 0x00, '#' = non-zero\n")
    for r in range(37):
        off = r * REC_SIZE
        rec = dec[off:off+REC_SIZE]
        bitmap = ''.join('#' if b != 0 else '.' for b in rec)
        grouped = ' '.join(bitmap[i:i+8] for i in range(0, 64, 8))
        nz = sum(1 for b in rec if b != 0)
        print(f"  rec {r:>3d} ({nz:>2d}nz): {grouped}")

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 8: ENTIRE FILE STRING SCAN (searching decoded for text)")
    print("=" * 80)
    # ================================================================

    # Also try on raw file (no XOR) to see if text is in plaintext somewhere
    raw_strs = extract_all_strings(raw, min_len=4)
    raw_seen = set()
    raw_unique = []
    for item in raw_strs:
        key = (item[0], item[2])
        if key not in raw_seen:
            raw_seen.add(key)
            raw_unique.append(item)
    raw_unique.sort(key=lambda x: x[1])
    if raw_unique:
        print("\nStrings found in RAW (un-XORed) file:")
        for stype, off, val in raw_unique[:50]:
            rec = off // REC_SIZE
            print(f"  0x{off:06X} (rec {rec:>4d}) [{stype:>5s}]: \"{val}\"")
    else:
        print("  No readable strings in raw file.")

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 9: LOOK FOR FORMULA SOURCE CODE PATTERNS")
    print("=" * 80)
    # ================================================================

    # TDX formula source often contains patterns like:
    # variable_name: expression;
    # Look for sequences of: identifier, colon, expression, semicolon
    # In GBK this might be variable names in ASCII + CJK comments

    print("\n--- Scanning for potential formula source blocks ---")
    # Look for runs of printable text longer than 30 chars (potential source)
    i = 0
    while i < len(dec):
        # Count consecutive printable/GBK bytes
        j = i
        while j < len(dec):
            b = dec[j]
            if 0x20 <= b <= 0x7e:
                j += 1
            elif 0x81 <= b <= 0xfe and j + 1 < len(dec):
                b2 = dec[j+1]
                if 0x40 <= b2 <= 0xfe and b2 != 0x7f:
                    j += 2
                else:
                    break
            elif b == 0x00:
                break
            else:
                break

        length = j - i
        if length >= 20:
            chunk = dec[i:j]
            rec = i // REC_SIZE
            for enc in ENCODINGS:
                try:
                    text = chunk.decode(enc)
                    if text.strip('\x00').strip():
                        print(f"\n  0x{i:06X} (rec {rec}), len={length} [{enc}]:")
                        print(f"    \"{text[:200]}\"")
                        # Check for TDX keywords
                        for kw in TDX_KW:
                            if kw in text.upper():
                                print(f"    ^ Contains keyword: {kw}")
                        break
                except:
                    pass
            i = j
        else:
            i += 1

    # ================================================================
    print("\n" + "=" * 80)
    print("PART 10: BYTE FREQUENCY ANALYSIS (metadata vs formula data)")
    print("=" * 80)
    # ================================================================

    meta_data = dec[:37*REC_SIZE]
    form_data = dec[99*REC_SIZE:699*REC_SIZE]

    for label, d in [("Metadata (rec 0-36)", meta_data), ("Formula (rec 99-698)", form_data)]:
        ctr = Counter(d)
        total = len(d)
        exp = total / 256
        chi2 = sum((ctr.get(i,0) - exp)**2 / exp for i in range(256))
        print(f"\n  {label}:")
        print(f"    Chi-squared: {chi2:.1f} ({'uniform/encrypted' if chi2 < 300 else 'skewed/plausible-text'})")
        top10 = ctr.most_common(10)
        for bv, cnt in top10:
            print(f"    0x{bv:02x}: {cnt:>5d} ({cnt/total*100:.1f}%)")
        missing = [i for i in range(256) if ctr.get(i, 0) == 0]
        if missing:
            print(f"    Missing bytes: {', '.join(f'0x{b:02x}' for b in missing[:20])}{'...' if len(missing)>20 else ''}")

    print("\n\nDone.")


if __name__ == '__main__':
    main()
