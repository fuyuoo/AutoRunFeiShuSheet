# TDX .tn6 Binary Format Analysis

## Files Downloaded from sqltxt/tdx

All files saved to: `D:\PythonWorkSpace\AutoRunFeiShuSheet\temp\github_pairs\`

### Paired Files (.tn6 + .txt)

| # | Binary (.tn6) | Source (.txt) | Binary Size | Source Size | Source Content |
|---|---------------|---------------|-------------|-------------|----------------|
| 1 | 净净资产收益率.tn6 | 净净资产收益率.txt | 6360 bytes | 32 bytes | `FINANCE(33)/FINANCE(34)*100>ROE;` |
| 2 | 市净率.tn6 | 市净率.txt | 6360 bytes | 35 bytes | `C/FINANCE(34)<PB AND FINANCE(34)>0;` |
| 3 | 市盈率.tn6 | 市盈率.txt | 6440 bytes | 16 bytes | `DYNAINFO(39)<PE;` |

### Additional .txt Files (source code only, no matching .tn6)

| File | Size | Description |
|------|------|-------------|
| ROE.txt | 38 bytes | `A:=FINANCE(30)/FINANCE(19)*100; A>=20;` |
| ROE2.txt | 31 bytes | `FINANCE(33)/FINANCE(34)*100>20;` |
| 基本面选股.txt | 112 bytes | Stock selection formula |
| 庄家控盘.txt | 750 bytes | Market maker control detection |
| 海底捞金.txt | 1190 bytes | Bottom fishing strategy |
| 跌破净资产.txt | 63 bytes | Below net asset value screen |
| 通达信财务函数.txt | 1874 bytes | TDX financial function reference |
| 三剑下天山.txt | 1387 bytes | Bollinger band + CCI + MA indicator |
| 主力风向标.txt | 2120 bytes | Main force direction indicator |

### Additional Binary Files

| File | Size | Type |
|------|------|------|
| dkx.tne | 6576 bytes | .tne format (older TDX formula format) |

---

## Binary Structure Analysis

### Header (bytes 0x00 - 0x2F, 48 bytes) -- IDENTICAL across all .tn6 files

```
0000: 3f 8a 19 97 6d a1 36 14 94 2f 1d 29 a7 7a a8 2d
0010: 00 f7 36 f3 88 94 69 06 99 2e 77 77 de 5b 4f bb
0020: 00 f7 36 f3 88 94 69 06 00 f7 36 f3 88 94 69 06
```

Magic signature: `3f 8a 19 97 6d a1 36 14`

The fill/padding pattern `00 f7 36 f3 88 94 69 06` (8 bytes) appears extensively throughout.

### Checksum (bytes 0x30 - 0x3F, 16 bytes) -- UNIQUE per file

```
净净资产收益率: 04 8b 96 93 25 bd 36 8d  ca e6 3e 72 4f dc 8c d9
市净率:        0e 47 32 0a 63 28 cf de  20 fb 05 95 43 23 be 03
市盈率:        63 37 04 f1 e5 66 49 a1  20 fb 05 95 43 23 be 03
```

Note: 市净率 and 市盈率 share the last 8 bytes: `20 fb 05 95 43 23 be 03`.

### Data Region Structure (bytes 0x40+)

**Block markers (8 bytes each):**
| Marker | Likely Role |
|--------|-------------|
| `03 6f 43 0b 02 32 b9 ab` | Formula entry marker |
| `03 55 80 a5 13 ae 4e 3c` | Block delimiter (repeating pattern start) |
| `58 47 d6 df fb bb a5 b5` | Block terminator (repeating pattern end) |
| `b7 2c 7f df 4e f2 4a 41` | Section marker |
| `54 1a 39 5c 67 64 bd ff` | Section terminator |
| `e0 fd d4 1b d9 a4 11 d7` | End-of-data marker |

**Data value patterns (8 bytes each):**
| Pattern | Context |
|---------|---------|
| `27 f6 a3 5d d2 03 c0 e1` | Common fill value in structured blocks (all files) |
| `d3 2d 10 df 72 fc 0a 62` | Data pattern in files 1 and 3 |
| `08 83 96 0d a9 e0 bf 67` | Data pattern in file 2 |

**Post-formula-marker values:**
| File | 8 bytes after formula marker |
|------|------------------------------|
| 净净资产收益率 | `3e a7 bf 36 c2 89 81 83` |
| 市净率 | `ff 26 e8 8f 6b c9 6b 95` |
| 市盈率 | `85 f8 17 c0 60 15 84 95` |

**Secondary data values (after fill + before main data):**
| File | 8 bytes |
|------|---------|
| 净净资产收益率 | `6e 3a 93 9a 1f 24 db 7b` |
| 市净率 | `ee 46 79 26 ea 0f ea 37` |
| 市盈率 | `c0 60 f1 3e c4 56 48 c8` |

### Repeating Block Pattern

After the initial header+data, there's a repeating macro-block structure (each ~136 bytes):

```
[03 55 80 a5 13 ae 4e 3c]  <- block start marker
[27 f6 a3 5d d2 03 c0 e1]  <- repeated 10 times
[58 47 d6 df fb bb a5 b5]  <- block end marker
[00 f7 36 f3 88 94 69 06]  <- fill x3
[b7 2c 7f df 4e f2 4a 41]  <- section marker
[27 f6 a3 5d d2 03 c0 e1]  <- repeated 10 times
[54 1a 39 5c 67 64 bd ff]  <- section terminator
[00 f7 36 f3 88 94 69 06]  <- fill x3
```

This pattern repeats ~10 times across the file.

### Byte Differences Between Files

| File A | File B | Different bytes | Total | Percentage |
|--------|--------|-----------------|-------|------------|
| 净净资产收益率 | 市净率 | 423 | 6360 | 6.7% |
| 净净资产收益率 | 市盈率 | 160 | 6360 | 2.5% |
| 市净率 | 市盈率 | 447 | 6360 | 7.0% |

Differences concentrate in:
- The checksum region (bytes 0x30-0x3F)
- The initial data block (bytes 0x70-0x8F)
- The end marker region (bytes 0x8B0-0x8CF)

---

## Key Observations

1. **Fixed file size**: Despite vastly different formula complexity (16-35 bytes source), all files are ~6.3KB. The format uses fixed-size blocks per formula token.

2. **Block-based encoding**: Each formula function/operand appears to occupy one or more 8-byte slots in a repeating block structure.

3. **Not simple XOR**: The data patterns don't match simple XOR encryption. The repeated `27 f6 a3 5d d2 03 c0 e1` blocks appear in all files regardless of source content, suggesting they may represent common structural elements.

4. **Checksum region**: The 16-byte checksum at offset 0x30 varies per file. Files 2 and 3 share the last 8 bytes.

5. **Potential block cipher**: The 8-byte alignment and distinct markers suggest a block cipher with 64-bit (8-byte) block size, or a fixed-width token encoding scheme.

6. **Formula functions are tokens**: Functions like FINANCE(), DYNAINFO(), CROSS() likely map to fixed binary tokens. The formula source size vs binary size ratio suggests heavy structural overhead.

## Next Steps for Reverse Engineering

1. Create trivially simple formulas (e.g., `A;`, `1+1;`, `CLOSE;`) and compile them to .tn6
2. Compare byte differences to isolate which blocks correspond to which tokens
3. Test if markers (`03 55...`, `58 47...`, etc.) correspond to specific TDX functions
4. Investigate the 16-byte checksum region for hash/verification algorithm
5. Look for known TDX decryption tools in Chinese developer communities
6. The .tne format (dkx.tne) may be an older/simpler format worth analyzing first
