# Smallest possible transparent PNG

> [Archived][archive_url] from the [original][original_url] on `2023-10-28T07:28:47Z`. All copyright
> lays with Gareth Rees. Only minor editing to the formatting has been done.

[Gareth Rees](mailto:gdr@garethrees.org), 2007-11-15

A detailed look at the encoding of bitmap images in the PNG file format, leading up to the
discovery of the smallest possible transparent PNG, only 67 bytes long.

[This discussion][rfc_2397_discussion] at [drj11’s blog][drj11_blog] raises the question of how
small is the smallest [Portable Network Graphics][libpng_pub] (PNG) image? Starting out with general
principles, it seems likely that we want the smallest possible image (PNG format doesn’t allow
empty images, so it’s going to have to be 1×1), with the smallest number of colour channels
(PNG supports greyscale images, with a single colour channel per pixel) and the smallest bit
depth per channel (PNG supports 1-bit channels).

Let’s get going by creating a 1×1 black-and-white image in GraphicConverter and save it as PNG.
The result is 73 bytes long. Is that the answer? Unfortunately it’s not easy to be sure. The PNG
standard has a fair bit of flexibility, so it might be the case that GraphicConverter is being
wasteful in some way. To see if this is the case, we have to look at GraphicConverter’s output
in detail. Here’s a hex dump:

```plain
00000000: 8950 4e47 0d0a 1a0a 0000 000d 4948 4452  .PNG........IHDR
00000010: 0000 0001 0000 0001 0100 0000 0037 6ef9  .............7n.
00000020: 2400 0000 1049 4441 5478 9c62 6001 0000  $....IDATx.b`...
00000030: 00ff ff03 0000 0600 0557 bfab d400 0000  .........W......
00000040: 0049 454e 44ae 4260 82                   .IEND.B`.
```

Referring to the [PNG specification][png_spec], those 73 bytes break down as follows:

* An 8-byte file signature.
* A 13-byte [`IHDR` chunk][png_ihdr_chunk] containing the image header, plus 12 bytes chunk overhead.
* A 16-byte [`IDAT` chunk][png_idat_chunk] containing the image data, plus 12 bytes chunk overhead.
* A 0-byte [`IEND` chunk][png_iend_chunk] marking the end of the file, plus 12 bytes chunk overhead.

You can see the location of the chunks clearly in the hex dump, because the ASCII chunk types
stand out. We can’t do anything about the size of the file signature or the `IHDR` and `IEND`
chunks, or the chunk overhead, as these are fixed in size. So any possibility for reduction must
lie in the `IDAT` chunk. This is a zlib data stream of the scanlines from the image, compressed
using the “DEFLATE” method. Using the [zlib specification][zlib_spec] (RFC 1950) we can decode
this zlib stream as follows:

* The header byte `78` meaning “deflate compression with a 32 KiB window”.
* The informational byte `9c` meaning “the default compression algorithm was used” (plus a checksum).
* 10 bytes of compressed data: `62 60 01 00 00 00 ff ff 03 00`.
* A 4-byte Adler32 checksum: `00 06 00 05`.

It’s easy to decompress the `IDAT` chunk in Python:

```py
>>> import zlib
>>> from binascii import unhexlify
>>> idat = unhexlify(b'789c626001000000ffff030000060005')
>>> zlib.decompress(idat)
b'\x00\x04'
```

What’s this pair of bytes? The section on [scanline serialization][png_spec_scanline_serialization]
in the PNG specification explains that the first byte, `00`, is the filter type for the first
scanline of the image (in this case 0 means “no filtering”) and the second byte, `04`, contains
the packed samples for pixels in the scanline. PNG is big-endian, so the single pixel value of
0 appears in the high bit of the byte; the remaining seven bits are unused (why they contain the
value 4 is a bit of a mystery). Now we can turn to the [DEFLATE Specification][deflate_spec]
(RFC 1951). A DEFLATE stream is a little-endian bit stream. So let’s write it out in little-endian order:

```plain
---62--- ---60--- ---01--- ---00--- ---00--- ---00--- ---ff--- ---ff--- ---03--- ---00---
01000110 00000110 10000000 00000000 00000000 00000000 11111111 11111111 11000000 00000000
\-------first block---------/\--------------second block--------------/ \--third block--/
```

It decodes as follows:

First block:

* `0` = not final block
* `10`<a href="#note-1" id="noteref-1">¹</a> = Huffman coding block with fixed codes
* `00110000` = literal byte `00`
* `00110100` = literal byte `04`
* `0000000` = end of block

Second block:

* `0` = not final block
* `00` = non compression block
* `000` = padding to end of byte
* `00000000 00000000` = number of data bytes in the block (that is, zero)
* `11111111 11111111` = one’s complement of number of data bytes

Third block:

* `1` = final block
* `10`<a href="#note-1" id="noteref-1-1">¹</a> = Huffman coding block with fixed codes
* `0000000` = end of block
* `000000` = padding to end of byte

The GraphicConverter encoding is clearly wasteful: the last two blocks contain no data and could
be dropped if we made the first block the final block by changing the first byte to `63`. And
indeed this is just what the zlib compression library outputs:

```py
>>> from binascii import hexlify
>>> hexlify(zlib.compress(b'\x00\x04'))
b'789c6360010000060005'
```

So did Thorsten Lemke, author of GraphicConverter, also write his own DEFLATE compressor?
(_No: [see update below](#update-2009-02-11)._) Anyway, putting the whole thing together:

```py
>>> import struct
>>> def chunk(type, data):
...     return (struct.pack('>I', len(data)) + type + data
...             + struct.pack('>I', zlib.crc32(type + data)))
>>> png = (b'\x89PNG\r\n\x1A\n'
...        + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 1, 0, 0, 0, 0))
...        + chunk(b'IDAT', zlib.compress(struct.pack('>BB', 0, 0)))
...        + chunk(b'IEND', b''))
...
>>> len(png)
67
```

So **67 bytes** is the answer to the question we started with.

But drj11’s original question was about PNGs with an alpha channel. When an alpha channel is
present, the smallest bit depth supported by the PNG format is 8 bits per channel. So a 1×1
transparent PNG has a five-byte scan line (one byte for the filter, one byte each for the red,
green, blue, and alpha channels).

```py
>>> hexlify(zlib.compress(b'\x00' * 5))
b'789c636000020000050001'
>>> len(_) / 2
11
```

Which makes a PNG **68 bytes** long. And indeed you can find the occasional [claim][slashdot_comment] that this is the smallest possible transparent PNG.

But in the case where the pixel is completely transparent (alpha = 0) it’s possible to shave off
one more byte by exploiting a feature of the DEFLATE compression format (or rather, exploiting
it slightly more cleverly than zlib is able to; _[see update below for why](#update-2009-07-01)_).
DEFLATE allows you to duplicate a portion of the output stream by referring to it with a special
pair 〈length of portion to duplicate, distance backwards〉. And crucially, the referenced string
is _allowed to overlap_ with the current position. As it says in the DEFLATE spec:

> if the last 2 bytes decoded have values X and Y, a string reference with 〈length = 5, distance
> = 2〉 adds X,Y,X,Y,X to the output stream.

So we can compress the five byte scanline by encoding a zero byte, then the string reference
〈length = 4, distance = 1〉, like this:

> `1` = final block
> `10` = Huffman coding block with fixed codes
> `00110000` = literal byte `00`
> `0000010` = duplicate string of length 4<a href="#note-2" id="noteref-2">²</a>
> `00000` = … and distance 1 before current position
> `0000000` = end of block
> `00` = padding to end of byte

That packs into 4 bytes:

```plain
---63--- ---00--- ---01--- ---00---
11000110 00000000 10000000 00000000
```

Plus the two bytes of zlib header, `78 9c`, and the Adler-32 checksum, `00 05 00 01`, makes 10
bytes. Putting the whole PNG together:

```py
>>> png = (b'\x89PNG\r\n\x1A\n'
...        + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
...        + chunk(b'IDAT', unhexlify(b'789c6300010000050001'))
...        + chunk(b'IEND', b''))
...
>>> len(png)
67
```

So, bandwidth misers using 1×1 transparent PNGs, read this article and save a byte!

## Updates

### Update 2009-02-11

I was wrong in my guess about GraphicConverter containing a custom DEFLATE implementation. It’s
possible to get the same output from zlib as from GraphicConverter _if you flush the encoding
stream before finalizing it_:

```py
>>> o = zlib.compressobj()
>>> hexlify(o.compress(b'\x00\x04'))
b'789c'
>>> hexlify(o.flush(zlib.Z_SYNC_FLUSH))
b'626001000000ffff'
>>> hexlify(o.flush(zlib.Z_FINISH))
b'030000060005'
```

The reason why flushing the encoding stream inserts a zero-length non-compression block is so
that the flushed stream is synchronized to a byte boundary. A non-final Huffman coding block can
finish anywhere within a byte, but a non-compression block always finishes on a byte boundary,
which is necessary for synchronization with byte-oriented protocols like the standard C library’s
file interface.

### Update 2009-07-01

There’s a systematic reason why zlib fails to find the best compression for this file. In
[`deflate.c`][google_deflate.c_codesearch] there’s even a comment to this effect:

```plain
/* To simplify the code, we prevent matches with the string of window index 0. */
```

If I read the code correctly, zlib never finds a repeat that starts on byte 0 of the data (in
fact, on byte 0 of the current “window” into the data). This allows a simplification of the loop
termination condition, and presumably speeds up the repeat-finding loop in the common case. So
when there’s a repeating sequence at the start of the data, it’s possible to find a better DEFLATE
compression than zlib.

## Footnotes

1. <a href="#noteref-1" id="note-1">↩</a> <a href="#noteref-1-1" id="note-1">↩</a> In the
   DEFLATE specification the authors do their best to confuse the reader by giving the block
   types in big-endian order despite everything else being in little-endian order: see section
   3.2.3 where block type “10” is given as “01” and vice versa.

2. <a href="#noteref-2" id="note-2">↩</a> A puzzled reader e-mailed me to query this explanation.
   It is indeed slightly confusing because there a two-step encoding here. Refer to the
   [DEFLATE Specification][deflate_spec]. In section 3.2.5 you’ll see that in the encoding of
   〈length, backward distance〉 pairs, a length of 4 is first encoded as the value 258 (to merge
   it into the same alphabet as literal bytes). Then in section 3.2.6, you’ll see that in the
   default Huffman coding tables (which are the ones in force in this case), codes from this
   merged alphabet in the range 256 through 279 are encoded in 7 bits as 0000000 through 0010111.
   So 256 is encoded as 0000000, 257 as 0000001, and 258 as 0000010.

[deflate_spec]: https://web.archive.org/web/20231028072847/http://www.ietf.org/rfc/rfc1951.txt
[rfc_2397_discussion]: https://web.archive.org/web/20231028072847/http://drj11.wordpress.com/2007/11/14/using-the-rfc-2397-data-url-scheme-to-micro-optimise-small-images/
[drj11_blog]: https://web.archive.org/web/20231028072847/http://drj11.wordpress.com/
[png_spec]: https://web.archive.org/web/20231028072847/http://www.w3.org/TR/PNG/
[libpng_pub]: https://web.archive.org/web/20231028072847/http://libpng.org/pub/png/
[png_ihdr_chunk]: https://web.archive.org/web/20231028072847/http://www.w3.org/TR/PNG/#11IHDR
[png_idat_chunk]: https://web.archive.org/web/20231028072847/http://www.w3.org/TR/PNG/#11ITAT
[png_iend_chunk]: https://web.archive.org/web/20231028072847/http://www.w3.org/TR/PNG/#11IEND
[zlib_spec]: https://web.archive.org/web/20231028072847/http://www.ietf.org/rfc/rfc1950.txt
[png_spec_scanline_serialization]: https://web.archive.org/web/20231028072847/http://www.w3.org/TR/PNG/#4Concepts.EncodingScanlineAbs
[slashdot_comment]: https://web.archive.org/web/20231028072847/http://slashdot.org/comments.pl?sid=2200&cid=1574036
[google_deflate.c_codesearch]: https://web.archive.org/web/20231028072847/http://www.google.com/codesearch/p?sa=N&cd=2&ct=rc#e_ObwTAVPyo/modules/zlib/src/deflate.c&q=file:deflate.c

[archive_url]: https://web.archive.org/web/20231028072847/https://garethrees.org/2007/11/14/pngcrush/
[original_url]: https://garethrees.org/2007/11/14/pngcrush/
