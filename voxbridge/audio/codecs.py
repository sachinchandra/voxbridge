"""Audio codec engine for VoxBridge.

Provides pure-Python G.711 mulaw/alaw encoding/decoding via lookup tables,
PCM16 passthrough, and optional Opus support. All codec conversion routes
through PCM16 as the intermediate (hub-and-spoke) format.
"""

from __future__ import annotations

import struct
from typing import Callable

from loguru import logger

from voxbridge.core.events import Codec

# ---------------------------------------------------------------------------
# G.711 mu-law lookup tables
# ---------------------------------------------------------------------------

# Bias for mu-law encoding
_MULAW_BIAS = 0x84
_MULAW_CLIP = 32635

# Pre-computed mu-law compress table: PCM16 sample -> mu-law byte
_MULAW_EXP_TABLE = [0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
                    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
                    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
                    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
                    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
                    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]


def _mulaw_encode_sample(sample: int) -> int:
    """Encode a single 16-bit PCM sample to mu-law (ITU-T G.711)."""
    # Determine sign
    if sample < 0:
        sign = 0x80
        sample = -sample
    else:
        sign = 0

    # Clip to valid range
    if sample > _MULAW_CLIP:
        sample = _MULAW_CLIP

    # Add bias
    sample = sample + _MULAW_BIAS

    # Find the exponent by looking at the position of the highest set bit
    exponent = 7
    exp_mask = 0x4000  # bit 14
    for _ in range(8):
        if sample & exp_mask:
            break
        exponent -= 1
        exp_mask >>= 1

    # Extract mantissa (4 bits)
    mantissa = (sample >> (exponent + 3)) & 0x0F

    # Combine and complement
    mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return mulaw_byte


# Pre-compute full decode table: mu-law byte -> PCM16 sample
# Uses the standard ITU-T G.711 decode formula:
#   t = (mantissa << 3) + 0x84
#   t <<= exponent
#   result = t - 0x84
_MULAW_DECODE_TABLE: list[int] = []
for _i in range(256):
    _v = ~_i & 0xFF
    _sign = _v & 0x80
    _exponent = (_v >> 4) & 0x07
    _mantissa = _v & 0x0F
    _t = (_mantissa << 3) + _MULAW_BIAS
    _t <<= _exponent
    _sample = _t - _MULAW_BIAS
    if _sign:
        _sample = -_sample
    _MULAW_DECODE_TABLE.append(_sample)

# Pre-compute full encode table: 16-bit unsigned index -> mu-law byte
_MULAW_ENCODE_TABLE: list[int] = []
for _i in range(65536):
    _s = _i if _i < 32768 else _i - 65536  # convert to signed
    _MULAW_ENCODE_TABLE.append(_mulaw_encode_sample(_s))


def mulaw_decode(data: bytes) -> bytes:
    """Decode mu-law bytes to PCM16 little-endian bytes."""
    out = bytearray(len(data) * 2)
    for i, b in enumerate(data):
        sample = _MULAW_DECODE_TABLE[b]
        struct.pack_into("<h", out, i * 2, sample)
    return bytes(out)


def mulaw_encode(data: bytes) -> bytes:
    """Encode PCM16 little-endian bytes to mu-law bytes."""
    n_samples = len(data) // 2
    out = bytearray(n_samples)
    for i in range(n_samples):
        sample = struct.unpack_from("<h", data, i * 2)[0]
        # Convert signed to unsigned index
        idx = sample & 0xFFFF
        out[i] = _MULAW_ENCODE_TABLE[idx]
    return bytes(out)


# ---------------------------------------------------------------------------
# G.711 A-law lookup tables
# ---------------------------------------------------------------------------

def _alaw_encode_sample(sample: int) -> int:
    """Encode a single 16-bit PCM sample to A-law."""
    sign = 0
    if sample < 0:
        sign = 0x80
        sample = -sample
    if sample > 32767:
        sample = 32767

    if sample >= 256:
        exponent = 7
        exp_mask = 0x4000
        while exponent > 1 and not (sample & exp_mask):
            exponent -= 1
            exp_mask >>= 1
        mantissa = (sample >> (exponent + 3)) & 0x0F
        alaw_byte = sign | (exponent << 4) | mantissa
    else:
        alaw_byte = sign | (sample >> 4)

    return alaw_byte ^ 0x55


# Pre-compute A-law decode table
_ALAW_DECODE_TABLE: list[int] = []
for _i in range(256):
    _v = _i ^ 0x55
    _sign = _v & 0x80
    _exponent = (_v >> 4) & 0x07
    _mantissa = _v & 0x0F
    if _exponent == 0:
        _sample = (_mantissa << 4) + 8
    else:
        _sample = ((_mantissa << 4) + 264) << (_exponent - 1)
    if _sign:
        _sample = -_sample
    _ALAW_DECODE_TABLE.append(_sample)

# Pre-compute A-law encode table
_ALAW_ENCODE_TABLE: list[int] = []
for _i in range(65536):
    _s = _i if _i < 32768 else _i - 65536
    _ALAW_ENCODE_TABLE.append(_alaw_encode_sample(_s))


def alaw_decode(data: bytes) -> bytes:
    """Decode A-law bytes to PCM16 little-endian bytes."""
    out = bytearray(len(data) * 2)
    for i, b in enumerate(data):
        sample = _ALAW_DECODE_TABLE[b]
        struct.pack_into("<h", out, i * 2, sample)
    return bytes(out)


def alaw_encode(data: bytes) -> bytes:
    """Encode PCM16 little-endian bytes to A-law bytes."""
    n_samples = len(data) // 2
    out = bytearray(n_samples)
    for i in range(n_samples):
        sample = struct.unpack_from("<h", data, i * 2)[0]
        idx = sample & 0xFFFF
        out[i] = _ALAW_ENCODE_TABLE[idx]
    return bytes(out)


# ---------------------------------------------------------------------------
# Opus (optional)
# ---------------------------------------------------------------------------

def _opus_available() -> bool:
    try:
        import opuslib  # noqa: F401
        return True
    except ImportError:
        return False


class OpusCodec:
    """Wrapper around opuslib for Opus encode/decode."""

    def __init__(self, sample_rate: int = 48000, channels: int = 1):
        import opuslib
        self._encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_VOIP)
        self._decoder = opuslib.Decoder(sample_rate, channels)
        self.sample_rate = sample_rate
        self.channels = channels

    def encode(self, pcm_data: bytes, frame_size: int = 960) -> bytes:
        return self._encoder.encode(pcm_data, frame_size)

    def decode(self, opus_data: bytes, frame_size: int = 960) -> bytes:
        return self._decoder.decode(opus_data, frame_size)


# ---------------------------------------------------------------------------
# Codec Registry
# ---------------------------------------------------------------------------

# Type for encode/decode functions: bytes -> bytes
CodecFunc = Callable[[bytes], bytes]


class CodecRegistry:
    """Hub-and-spoke codec conversion registry.

    All conversions route through PCM16 as the intermediate format.
    This means we only need N encoders + N decoders instead of N^2 converters.

    Usage:
        registry = CodecRegistry()
        pcm_data = registry.decode(mulaw_bytes, Codec.MULAW)
        alaw_data = registry.encode(pcm_data, Codec.ALAW)
        # Or convert directly:
        alaw_data = registry.convert(mulaw_bytes, Codec.MULAW, Codec.ALAW)
    """

    def __init__(self) -> None:
        # Decoders: codec -> PCM16
        self._decoders: dict[Codec, CodecFunc] = {
            Codec.MULAW: mulaw_decode,
            Codec.ALAW: alaw_decode,
            Codec.PCM16: lambda x: x,  # passthrough
        }
        # Encoders: PCM16 -> codec
        self._encoders: dict[Codec, CodecFunc] = {
            Codec.MULAW: mulaw_encode,
            Codec.ALAW: alaw_encode,
            Codec.PCM16: lambda x: x,  # passthrough
        }

        # Register Opus if available
        if _opus_available():
            self._opus = OpusCodec()
            self._decoders[Codec.OPUS] = self._opus.decode
            self._encoders[Codec.OPUS] = self._opus.encode
            logger.debug("Opus codec registered")
        else:
            self._opus = None
            logger.debug("Opus codec not available (install opuslib)")

    def decode(self, data: bytes, codec: Codec) -> bytes:
        """Decode from any supported codec to PCM16."""
        if codec not in self._decoders:
            raise ValueError(f"No decoder registered for codec: {codec}")
        return self._decoders[codec](data)

    def encode(self, pcm_data: bytes, codec: Codec) -> bytes:
        """Encode PCM16 data to any supported codec."""
        if codec not in self._encoders:
            raise ValueError(f"No encoder registered for codec: {codec}")
        return self._encoders[codec](pcm_data)

    def convert(self, data: bytes, from_codec: Codec, to_codec: Codec) -> bytes:
        """Convert audio data from one codec to another (via PCM16 hub)."""
        if from_codec == to_codec:
            return data
        pcm = self.decode(data, from_codec)
        return self.encode(pcm, to_codec)

    def register_decoder(self, codec: Codec, func: CodecFunc) -> None:
        """Register a custom decoder."""
        self._decoders[codec] = func

    def register_encoder(self, codec: Codec, func: CodecFunc) -> None:
        """Register a custom encoder."""
        self._encoders[codec] = func

    @property
    def supported_codecs(self) -> list[Codec]:
        """List codecs that have both encoder and decoder."""
        return [c for c in Codec if c in self._decoders and c in self._encoders]


# Global singleton
codec_registry = CodecRegistry()
