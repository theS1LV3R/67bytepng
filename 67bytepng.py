#!/usr/bin/env python
# -*- coding: utf8 -*-
# vi: filetype=python tabsize=4 shiftwidth=4

# Taken (and slightly modified) from https://garethrees.org/2007/11/14/pngcrush/
# Archived: https://web.archive.org/web/20231028072847/https://garethrees.org/2007/11/14/pngcrush/

from struct import pack
from binascii import unhexlify
from zlib import crc32

filename = "67bytepng.png"


def chunk(type: bytes, data: bytes):
    return (pack('>I', len(data)) + type + data
            + pack('>I', crc32(type + data)))


def hexdump(bytestring):
    # For every 16th byte
    for i in range(0, len(bytestring), 16):
        # Assemble a list of bytes, being the current through the next 16 bytes
        chunk = bytestring[i:i+16]

        # Convert chunk to hex format
        hex_chunk = ' '.join(f'{b:02X}' for b in chunk)

        # Convert chunk to character format for display
        text_chunk = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)

        # Print each line of the hexdump
        print(f'{i:08X}: {hex_chunk.ljust(48)} {text_chunk}')


print("Assembling png data")

png = (
    # PNG magic bytes:
    # 89 50 4E 47 0D 0A 1A 0A
    # ‰  P  N  G  ␍ ␊  ␚ ␊
    b'\x89PNG\x0D\x0A\x1A\x0A'
    + chunk(b'IHDR', pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
    + chunk(b'IDAT', unhexlify(b'789c6300010000050001'))
    + chunk(b'IEND', b'')
)

print(f"Created png, len {len(png)}. Hex dump:")
hexdump(png)

# Open the file for writing in binary mode and write the PNG data
with open(filename, "wb") as file:
    print(f"Writing to {filename}")
    file.write(png)

print("Done!")
