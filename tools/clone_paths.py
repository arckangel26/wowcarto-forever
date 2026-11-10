"""Bounded, read-only decoding of observed native 1.20 vector/surface commands.

Geometry is source-bound to native serialization 5394F0/5396BC and drawing
parser 52F748. B/I/M and unknown commands are deliberately left opaque.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import struct

from tools.clone_regions import decode_region_outline


MAX_PATH_POINTS = 4096
_WORLD_LIMIT = (2 ** 31) / 256
_HEX = re.compile(r'[0-9A-Fa-f]+\Z', re.ASCII)
_OPACITY = (0x33, 0x55, 0x66, 0x88, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF)


@dataclass(frozen=True)
class DecodedNativePath:
    kind: str
    points: tuple[tuple[float, float], ...]
    closed: bool
    always_visible: bool
    opacity: int
    raw_options: str = ''
    fill_opacity: int = 0


def _coordinate(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > _WORLD_LIMIT:
        raise ValueError('Invalid native scene coordinate')
    return float(value)


def _marker_world(row, tile):
    if 'wx' in row and 'wy' in row:
        return _coordinate(row['wx']), _coordinate(row['wy'])
    return (_coordinate(tile['x']) + _coordinate(row['x']) / 256,
            _coordinate(tile['y']) + _coordinate(row['y']) / 256)


def decode_native_path(row, tile=None):
    """Return immutable world points and proven flags, or None for unsupported data.

    V_: four option digits, first unsigned tile-local 16-bit X/Y, then signed
    16-bit deltas. S_: first signed global 32-bit X/Y, then the same deltas.
    Native display Y is inverted for deltas, so Y -= dy. No game coordinates
    or Forever calibration are inferred here; callers can project the result.
    """
    encoded = row.get('links', '')
    if not isinstance(encoded, str) or encoded[:2] not in ('V_', 'S_'):
        return None
    prefix = encoded[:2]
    initial_chars = 14 if prefix == 'V_' else 18
    minimum_points = 2 if prefix == 'V_' else 3
    size = len(encoded)
    if (size < initial_chars + (minimum_points - 1) * 8 or
            size > initial_chars + (MAX_PATH_POINTS - 1) * 8 or
            (size - initial_chars) % 8):
        return None
    geometry = encoded[6:] if prefix == 'V_' else encoded[2:]
    if not _HEX.fullmatch(geometry):
        return None
    try:
        if prefix == 'S_':
            wx, wy = _marker_world(row, tile)
            points = decode_region_outline(dict(row, wx=wx, wy=wy))
            if points is None:
                return None
            points = tuple((_coordinate(x), _coordinate(y)) for x, y in points)
            # Native loader 4E2AD4: surface stroke DD, fill 33 alpha.
            return DecodedNativePath('S', points, True, False, 0xDD, fill_opacity=0x33)
        options = encoded[2:6]
        if tile is None or not re.fullmatch(r'[0-9]{4}', options, re.ASCII):
            return None
        tx, ty = _coordinate(tile['x']), _coordinate(tile['y'])
        data = bytes.fromhex(geometry)
        x, y = struct.unpack_from('>HH', data)
        points = [(_coordinate(tx + x / 256), _coordinate(ty + y / 256))]
        for offset in range(4, len(data), 4):
            dx, dy = struct.unpack_from('>hh', data, offset)
            x += dx
            y -= dy
            points.append((_coordinate(tx + x / 256), _coordinate(ty + y / 256)))
        # Loader 4E2A87/4E2AA6 reads the first and third option digits only.
        # Preserve the others; their full semantics are not established here.
        return DecodedNativePath('V', tuple(points), False, options[0] == '1',
                                 _OPACITY[int(options[2])], raw_options=options)
    except (KeyError, TypeError, ValueError, OverflowError, struct.error):
        return None
