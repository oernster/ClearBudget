#!/usr/bin/env python3
"""macOS icon generation and DMG volume-icon embedding for ClearBudget.

Split out of builddmg.py so each build module stays within the project's
400-line structural limit.  Contains the pure-Python PNG background compositor
(no Pillow dependency), the .icns generator, and the routine that embeds a
custom volume icon into a finished DMG.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

from build_utils import run, section


def _fill_png_background(path: Path, bg: tuple[int, int, int]) -> None:
    """Composite an RGBA PNG over a solid RGB background colour in-place.

    macOS renders ICNS icons against whatever surface is below them (white in
    Finder/installation windows).  Without an opaque background the transparent
    areas of the icon look white there, while appearing dark in the dark-themed
    app UI.  Filling the background once at ICNS-generation time makes the icon
    consistent everywhere.
    """
    data = path.read_bytes()
    pos, width, height, idat_chunks = 8, 0, 0, []
    while pos < len(data) - 12:
        n = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        cdata = data[pos + 8 : pos + 8 + n]
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", cdata[0:8])
            if cdata[8] != 8 or cdata[9] != 6:
                return  # not 8-bit RGBA — leave as-is
        elif ctype == b"IDAT":
            idat_chunks.append(cdata)
        pos += 12 + n

    bpp = 4
    filtered = bytearray(zlib.decompress(b"".join(idat_chunks)))
    stride = width * bpp + 1
    pixels = bytearray(height * width * bpp)

    def _paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    for r in range(height):
        filt = filtered[r * stride]
        row = r * width * bpp
        prev_row = (r - 1) * width * bpp
        for i in range(width * bpp):
            x = filtered[r * stride + 1 + i]
            a = pixels[row + i - bpp] if i >= bpp else 0
            b = pixels[prev_row + i] if r > 0 else 0
            c = pixels[prev_row + i - bpp] if r > 0 and i >= bpp else 0
            if filt == 0:
                pixels[row + i] = x
            elif filt == 1:
                pixels[row + i] = (x + a) & 0xFF
            elif filt == 2:
                pixels[row + i] = (x + b) & 0xFF
            elif filt == 3:
                pixels[row + i] = (x + (a + b) // 2) & 0xFF
            elif filt == 4:
                pixels[row + i] = (x + _paeth(a, b, c)) & 0xFF

    br, bg_, bb = bg
    for idx in range(width * height):
        off = idx * 4
        pa = pixels[off + 3]
        if pa == 255:
            continue
        if pa == 0:
            pixels[off], pixels[off + 1], pixels[off + 2], pixels[off + 3] = (
                br,
                bg_,
                bb,
                255,
            )
        else:
            a = pa / 255.0
            pixels[off] = int(pixels[off] * a + br * (1 - a))
            pixels[off + 1] = int(pixels[off + 1] * a + bg_ * (1 - a))
            pixels[off + 2] = int(pixels[off + 2] * a + bb * (1 - a))
            pixels[off + 3] = 255

    raw_out = bytearray()
    for r in range(height):
        raw_out.append(0)
        raw_out.extend(pixels[r * width * bpp : (r + 1) * width * bpp])

    def _chunk(name: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(name + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", crc)

    ihdr_payload = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_out = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr_payload)
        + _chunk(b"IDAT", zlib.compress(bytes(raw_out), 6))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png_out)


def png_to_icns(png_path: Path, work_dir: Path, bg: tuple[int, int, int]) -> Path:
    iconset = work_dir / "clearbudget.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 128, 256, 512]
    for size in sizes:
        for suffix, px in [
            (f"icon_{size}x{size}.png", size),
            (f"icon_{size}x{size}@2x.png", size * 2),
        ]:
            out = iconset / suffix
            run(
                ["sips", "-z", str(px), str(px), str(png_path), "--out", str(out)],
                capture_output=True,
            )
            _fill_png_background(out, bg)
    icns_path = work_dir / "clearbudget.icns"
    run(["iconutil", "--convert", "icns", str(iconset), "--output", str(icns_path)])
    shutil.rmtree(iconset)
    return icns_path


def _find_mount_point(hdiutil_stdout: str) -> str | None:
    for line in hdiutil_stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[-1].strip().startswith("/Volumes/"):
            return parts[-1].strip()
    return None


def set_volume_icon(icns_path: Path, final_dmg: str, rw_dmg_name: str) -> None:
    section("Set volume icon")
    rw_dmg = Path(rw_dmg_name)

    run(["hdiutil", "convert", final_dmg, "-format", "UDRW", "-o", str(rw_dmg)])
    try:
        result = subprocess.run(
            ["hdiutil", "attach", "-noverify", str(rw_dmg)],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"  $ hdiutil attach -noverify {rw_dmg}")
        mount_point = _find_mount_point(result.stdout)
        if not mount_point:
            sys.exit(
                f"ERROR: could not find mount point in hdiutil output:\n{result.stdout}"
            )

        try:
            shutil.copy(icns_path, Path(mount_point) / ".VolumeIcon.icns")
            set_file = subprocess.run(
                ["xcrun", "-f", "SetFile"], capture_output=True, text=True
            ).stdout.strip()
            if set_file:
                subprocess.run([set_file, "-a", "C", mount_point], check=True)
            else:
                finder_info = bytearray(32)
                finder_info[8] = 0x04
                subprocess.run(
                    [
                        "xattr",
                        "-wx",
                        "com.apple.FinderInfo",
                        " ".join(f"{b:02x}" for b in finder_info),
                        mount_point,
                    ],
                    check=True,
                )
            print(f"  Volume icon embedded; custom-icon flag set on {mount_point}")
        finally:
            run(["hdiutil", "detach", mount_point], check=False)

        Path(final_dmg).unlink(missing_ok=True)
        run(["hdiutil", "convert", str(rw_dmg), "-format", "UDZO", "-o", final_dmg])
    finally:
        rw_dmg.unlink(missing_ok=True)
