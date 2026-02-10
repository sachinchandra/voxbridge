"""Audio sample rate conversion for VoxBridge.

Provides simple linear interpolation resampling for converting between
common telephony sample rates (8kHz, 16kHz, 48kHz). All audio is
assumed to be PCM16 little-endian mono.
"""

from __future__ import annotations

import struct


def resample(data: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample PCM16 little-endian audio from one sample rate to another.

    Uses linear interpolation. For production quality, consider using
    scipy.signal.resample or a dedicated library.

    Args:
        data: PCM16 little-endian audio bytes.
        from_rate: Source sample rate in Hz.
        to_rate: Target sample rate in Hz.

    Returns:
        Resampled PCM16 little-endian audio bytes.
    """
    if from_rate == to_rate:
        return data

    n_samples = len(data) // 2
    if n_samples == 0:
        return b""

    # Unpack all samples
    samples = struct.unpack(f"<{n_samples}h", data)

    ratio = from_rate / to_rate
    out_len = int(n_samples / ratio)

    out_samples = []
    for i in range(out_len):
        src_pos = i * ratio
        src_idx = int(src_pos)
        frac = src_pos - src_idx

        if src_idx + 1 < n_samples:
            # Linear interpolation
            sample = samples[src_idx] * (1.0 - frac) + samples[src_idx + 1] * frac
        else:
            sample = samples[min(src_idx, n_samples - 1)]

        # Clamp to int16 range
        sample = max(-32768, min(32767, int(sample)))
        out_samples.append(sample)

    return struct.pack(f"<{len(out_samples)}h", *out_samples)


class Resampler:
    """Stateful resampler that tracks source/target rates.

    Usage:
        resampler = Resampler(from_rate=8000, to_rate=16000)
        upsampled = resampler.process(audio_8k)
    """

    def __init__(self, from_rate: int, to_rate: int) -> None:
        self.from_rate = from_rate
        self.to_rate = to_rate

    def process(self, data: bytes) -> bytes:
        """Resample a chunk of PCM16 audio."""
        return resample(data, self.from_rate, self.to_rate)

    @property
    def needs_resample(self) -> bool:
        """Whether this resampler actually changes the sample rate."""
        return self.from_rate != self.to_rate
