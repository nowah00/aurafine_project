"""utils/analyzer.py — RMS / LUFS / 공명 피크 헬퍼 테스트."""

import numpy as np
import pytest

from tests.conftest import sine, stereo
from utils.analyzer import compute_lufs, compute_rms, find_resonant_peaks


class TestComputeRms:
    def test_sine_rms_is_amplitude_over_sqrt2(self, sample_rate):
        # 사인파의 RMS는 이론적으로 진폭 / √2 이다.
        signal = sine(1000.0, 1.0, amplitude=0.5)
        assert compute_rms(signal) == pytest.approx(0.5 / np.sqrt(2), rel=1e-3)

    def test_silence_is_zero(self):
        assert compute_rms(np.zeros(1000, dtype=np.float32)) == 0.0

    def test_empty_returns_zero(self):
        assert compute_rms(np.array([], dtype=np.float32)) == 0.0

    def test_stereo_averages_both_channels(self):
        # 왼쪽만 소리가 있으면 전체 평균 에너지는 절반 → RMS는 1/√2 배.
        left = sine(1000.0, 1.0, amplitude=0.5)
        signal = stereo(left, np.zeros_like(left))
        expected = compute_rms(left) / np.sqrt(2)
        assert compute_rms(signal) == pytest.approx(expected, rel=1e-3)


class TestComputeLufs:
    def test_silence_is_negative_infinity(self, sample_rate):
        silence = np.zeros(sample_rate, dtype=np.float32)
        assert compute_lufs(silence, sample_rate) == float("-inf")

    def test_empty_returns_negative_infinity(self, sample_rate):
        assert compute_lufs(np.array([], dtype=np.float32), sample_rate) == float("-inf")

    def test_louder_signal_has_higher_lufs(self, sample_rate):
        quiet = sine(1000.0, 3.0, amplitude=0.1)
        loud = sine(1000.0, 3.0, amplitude=0.5)
        assert compute_lufs(loud, sample_rate) > compute_lufs(quiet, sample_rate)

    def test_doubling_amplitude_raises_lufs_by_6db(self, sample_rate):
        # 진폭 2배 = +6dB. LUFS도 정확히 6dB 올라가야 한다.
        quiet = sine(1000.0, 3.0, amplitude=0.2)
        loud = sine(1000.0, 3.0, amplitude=0.4)
        difference = compute_lufs(loud, sample_rate) - compute_lufs(quiet, sample_rate)
        assert difference == pytest.approx(6.02, abs=0.1)

    def test_accepts_stereo(self, sample_rate):
        mono = sine(1000.0, 3.0, amplitude=0.3)
        value = compute_lufs(stereo(mono, mono), sample_rate)
        assert np.isfinite(value)


class TestFindResonantPeaks:
    def test_finds_the_tone_frequency(self, sample_rate):
        signal = sine(1000.0, 1.0, amplitude=0.5)
        peaks = find_resonant_peaks(signal, sample_rate)
        assert peaks, "피크를 하나도 찾지 못했습니다."
        # STFT 해상도(약 21Hz/bin)를 감안해 넉넉히 비교한다.
        assert peaks[0] == pytest.approx(1000.0, abs=50.0)

    def test_empty_returns_empty_list(self, sample_rate):
        assert find_resonant_peaks(np.array([], dtype=np.float32), sample_rate) == []

    def test_respects_max_peaks(self, sample_rate):
        signal = sine(500.0, 1.0) + sine(1500.0, 1.0) + sine(3000.0, 1.0)
        assert len(find_resonant_peaks(signal, sample_rate, max_peaks=2)) <= 2

    def test_peaks_stay_in_voice_range(self, sample_rate):
        # 200~8000Hz 밖의 성분(60Hz, 15kHz)은 후보에서 빠져야 한다.
        signal = sine(60.0, 1.0) + sine(1000.0, 1.0) + sine(15000.0, 1.0)
        for frequency in find_resonant_peaks(signal, sample_rate):
            assert 200.0 <= frequency <= 8000.0
