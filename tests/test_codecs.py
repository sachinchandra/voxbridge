"""Tests for the VoxBridge codec engine."""

import struct

import pytest

from voxbridge.audio.codecs import (
    CodecRegistry,
    alaw_decode,
    alaw_encode,
    mulaw_decode,
    mulaw_encode,
)
from voxbridge.audio.resampler import Resampler, resample
from voxbridge.core.events import Codec


class TestMulaw:
    """Tests for G.711 mu-law codec."""

    def test_encode_decode_roundtrip(self):
        """Encoding then decoding should approximately recover the original."""
        # Generate a simple sine-like pattern in PCM16
        samples = [0, 1000, 5000, 10000, 20000, 30000, 32000]
        samples += [-x for x in samples]

        for sample in samples:
            pcm_bytes = struct.pack("<h", sample)
            encoded = mulaw_encode(pcm_bytes)
            decoded = mulaw_decode(encoded)
            recovered = struct.unpack("<h", decoded)[0]

            # Mu-law is lossy but should be within ~2% for large values
            if abs(sample) > 100:
                assert abs(recovered - sample) < abs(sample) * 0.15, \
                    f"Sample {sample} -> encoded -> {recovered} (too much error)"

    def test_silence(self):
        """Silence (0) should roundtrip cleanly."""
        pcm_silence = struct.pack("<h", 0)
        encoded = mulaw_encode(pcm_silence)
        decoded = mulaw_decode(encoded)
        recovered = struct.unpack("<h", decoded)[0]
        assert abs(recovered) < 10  # Close to 0

    def test_encode_length(self):
        """Mu-law encodes 2 PCM bytes to 1 mu-law byte."""
        pcm = b"\x00" * 100  # 50 samples
        encoded = mulaw_encode(pcm)
        assert len(encoded) == 50

    def test_decode_length(self):
        """Mu-law decodes 1 mu-law byte to 2 PCM bytes."""
        mulaw_data = bytes(range(100))
        decoded = mulaw_decode(mulaw_data)
        assert len(decoded) == 200

    def test_batch_roundtrip(self):
        """Multiple samples should roundtrip together."""
        n_samples = 160  # 20ms at 8kHz
        pcm = struct.pack(f"<{n_samples}h", *([1000] * n_samples))
        encoded = mulaw_encode(pcm)
        decoded = mulaw_decode(encoded)
        assert len(decoded) == len(pcm)


class TestAlaw:
    """Tests for G.711 A-law codec."""

    def test_encode_decode_roundtrip(self):
        """A-law roundtrip should approximately recover the original."""
        samples = [0, 500, 2000, 8000, 16000, 30000]
        samples += [-x for x in samples]

        for sample in samples:
            pcm_bytes = struct.pack("<h", sample)
            encoded = alaw_encode(pcm_bytes)
            decoded = alaw_decode(encoded)
            recovered = struct.unpack("<h", decoded)[0]

            if abs(sample) > 100:
                assert abs(recovered - sample) < abs(sample) * 0.2, \
                    f"Sample {sample} -> encoded -> {recovered} (too much error)"

    def test_encode_length(self):
        """A-law encodes 2 PCM bytes to 1 A-law byte."""
        pcm = b"\x00" * 64
        encoded = alaw_encode(pcm)
        assert len(encoded) == 32

    def test_decode_length(self):
        """A-law decodes 1 byte to 2 PCM bytes."""
        alaw_data = bytes(range(50))
        decoded = alaw_decode(alaw_data)
        assert len(decoded) == 100


class TestCodecRegistry:
    """Tests for the CodecRegistry hub-and-spoke conversion."""

    def test_supported_codecs(self):
        """Registry should support at least PCM16, MULAW, ALAW."""
        registry = CodecRegistry()
        supported = registry.supported_codecs
        assert Codec.PCM16 in supported
        assert Codec.MULAW in supported
        assert Codec.ALAW in supported

    def test_pcm16_passthrough(self):
        """PCM16 encode/decode should be identity."""
        registry = CodecRegistry()
        data = b"\x01\x02\x03\x04"
        assert registry.decode(data, Codec.PCM16) == data
        assert registry.encode(data, Codec.PCM16) == data

    def test_convert_same_codec(self):
        """Converting between the same codec should return the same data."""
        registry = CodecRegistry()
        data = b"\xff" * 100
        assert registry.convert(data, Codec.MULAW, Codec.MULAW) == data

    def test_convert_mulaw_to_alaw(self):
        """Should be able to convert between mu-law and A-law via PCM16."""
        registry = CodecRegistry()
        # Create some mu-law data
        pcm = struct.pack("<10h", *([5000] * 10))
        mulaw_data = mulaw_encode(pcm)

        # Convert mu-law -> a-law
        alaw_data = registry.convert(mulaw_data, Codec.MULAW, Codec.ALAW)
        assert len(alaw_data) == len(mulaw_data)

        # Decode the A-law and check it's close to the original
        recovered_pcm = alaw_decode(alaw_data)
        recovered_samples = struct.unpack("<10h", recovered_pcm)
        for sample in recovered_samples:
            assert abs(sample - 5000) < 1000  # Lossy but reasonable

    def test_unsupported_codec_raises(self):
        """Should raise ValueError for unknown codecs."""
        registry = CodecRegistry()
        with pytest.raises(ValueError):
            registry.decode(b"\x00", Codec.OPUS)  # Opus not available in test

    def test_register_custom_codec(self):
        """Should be able to register custom encode/decode functions."""
        registry = CodecRegistry()

        # Register a dummy "codec"
        registry.register_decoder(Codec.OPUS, lambda data: data * 2)
        registry.register_encoder(Codec.OPUS, lambda data: data[:len(data)//2])

        assert Codec.OPUS in registry.supported_codecs
        assert registry.decode(b"\x01\x02", Codec.OPUS) == b"\x01\x02\x01\x02"


class TestResampler:
    """Tests for audio resampling."""

    def test_identity(self):
        """Same rate should return identical data."""
        data = struct.pack("<10h", *range(10))
        result = resample(data, 8000, 8000)
        assert result == data

    def test_upsample_2x(self):
        """8kHz -> 16kHz should double the number of samples."""
        n = 100
        data = struct.pack(f"<{n}h", *([1000] * n))
        result = resample(data, 8000, 16000)
        assert len(result) == n * 2 * 2  # 200 samples * 2 bytes each

    def test_downsample_2x(self):
        """16kHz -> 8kHz should halve the number of samples."""
        n = 200
        data = struct.pack(f"<{n}h", *([1000] * n))
        result = resample(data, 16000, 8000)
        assert len(result) == n * 2 // 2  # 100 samples * 2 bytes each

    def test_resampler_class(self):
        """Resampler class should work the same as the function."""
        resampler = Resampler(8000, 16000)
        assert resampler.needs_resample is True

        data = struct.pack("<50h", *([500] * 50))
        result = resampler.process(data)
        assert len(result) == 200  # 100 samples * 2 bytes

    def test_no_resample_needed(self):
        """Resampler with same rates should report no resample needed."""
        resampler = Resampler(8000, 8000)
        assert resampler.needs_resample is False

    def test_empty_data(self):
        """Empty input should return empty output."""
        assert resample(b"", 8000, 16000) == b""
