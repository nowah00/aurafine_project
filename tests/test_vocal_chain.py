"""pipeline/vocal_chain.py — 보컬 체인(HPF → 디에서 → EQ → 컴프 → 리버브) 테스트.

디에서 임계값 자체는 아직 실제 보컬로 검증되지 않았으므로(current-task.md 참고),
여기서는 "치찰음이 줄어드는 방향인가" 같은 정성적 성질만 확인한다.
"""

import numpy as np
import pytest

from pipeline.vocal_chain import _deess, process_vocal
from tests.conftest import band_energy, sine


class TestProcessVocal:
    @pytest.mark.parametrize("preset", ["dry", "pop", "ballad"])
    def test_every_preset_runs_and_keeps_length(self, preset, sample_rate):
        vocal = sine(440.0, 1.0, amplitude=0.3)
        processed = process_vocal(vocal, sample_rate, reverb=preset)
        assert processed.shape == vocal.shape
        assert processed.dtype == np.float32
        assert np.all(np.isfinite(processed))

    def test_invalid_preset_raises(self, sample_rate):
        with pytest.raises(ValueError):
            process_vocal(sine(440.0, 0.5), sample_rate, reverb="hall")

    def test_empty_returns_empty(self, sample_rate):
        assert process_vocal(np.array([], dtype=np.float32), sample_rate).size == 0

    def test_highpass_removes_low_rumble(self, sample_rate):
        """100Hz 하이패스: 40Hz 저음 잡음이 크게 줄어야 한다."""
        vocal = sine(440.0, 1.0, amplitude=0.3) + sine(40.0, 1.0, amplitude=0.3)
        processed = process_vocal(vocal, sample_rate, reverb="dry")

        before = band_energy(vocal, 20.0, 60.0, sample_rate)
        after = band_energy(processed, 20.0, 60.0, sample_rate)
        assert after < before * 0.1

    def test_keeps_the_vocal_fundamental(self, sample_rate):
        # 저음은 깎되 본 음역대(440Hz)는 살아 있어야 한다.
        vocal = sine(440.0, 1.0, amplitude=0.3)
        processed = process_vocal(vocal, sample_rate, reverb="dry")
        assert band_energy(processed, 400.0, 480.0, sample_rate) > 0.0

    def test_reverb_adds_energy_compared_to_dry(self, sample_rate):
        vocal = sine(440.0, 1.0, amplitude=0.3)
        dry = process_vocal(vocal, sample_rate, reverb="dry")
        ballad = process_vocal(vocal, sample_rate, reverb="ballad")
        # 리버브가 실제로 신호를 바꿨는지만 확인한다.
        assert not np.allclose(dry, ballad, atol=1e-4)


class TestDeesser:
    """디에서는 private 헬퍼지만, '다이내믹 동작' 자체가 회귀 방지 대상이라 직접 검증한다."""

    def test_reduces_a_sibilance_burst(self, sample_rate):
        # 1초 내내 있는 8kHz + 중간 0.2초 구간만 훨씬 커지는 치찰음 버스트.
        base = sine(8000.0, 1.0, amplitude=0.05)
        burst = np.zeros_like(base)
        start, end = int(sample_rate * 0.4), int(sample_rate * 0.6)
        burst[start:end] = sine(8000.0, 0.2, amplitude=0.5)
        signal = (base + burst).astype(np.float32)

        deessed = _deess(signal, sample_rate)

        before = band_energy(signal[start:end], 6000.0, 10000.0, sample_rate)
        after = band_energy(deessed[start:end], 6000.0, 10000.0, sample_rate)
        assert after < before, "치찰음 구간이 전혀 줄지 않았습니다."

    def test_leaves_a_steady_signal_mostly_alone(self, sample_rate):
        """정적 EQ가 아님을 확인: 레벨이 일정하면 크게 깎지 않는다."""
        steady = sine(8000.0, 1.0, amplitude=0.3)
        deessed = _deess(steady, sample_rate)

        before = band_energy(steady, 6000.0, 10000.0, sample_rate)
        after = band_energy(deessed, 6000.0, 10000.0, sample_rate)
        # -8dB(에너지 기준 약 0.16배)까지 깎이는 게 최대치이므로 그보다는 커야 한다.
        assert after > before * 0.5

    def test_does_not_touch_frequencies_outside_the_band(self, sample_rate):
        signal = sine(440.0, 1.0, amplitude=0.3)
        deessed = _deess(signal, sample_rate)
        before = band_energy(signal, 300.0, 600.0, sample_rate)
        after = band_energy(deessed, 300.0, 600.0, sample_rate)
        assert after == pytest.approx(before, rel=0.05)

    def test_silence_is_returned_unchanged(self, sample_rate):
        silence = np.zeros(sample_rate, dtype=np.float32)
        np.testing.assert_array_equal(_deess(silence, sample_rate), silence)

    def test_output_is_float32(self, sample_rate):
        assert _deess(sine(8000.0, 0.5), sample_rate).dtype == np.float32
