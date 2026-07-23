"""pipeline/master.py — 커스텀 브릭월 리미터 + LUFS 정규화 테스트.

여기 테스트 상당수는 회귀 방지용이다: pedalboard.Limiter는 자동 메이크업
게인과 ceiling 오버슛 문제가 있어 직접 구현으로 대체했으므로, 그 두 성질을
계속 지키는지 확인한다.
"""

import numpy as np
import pytest

from pipeline.master import limit, master
from tests.conftest import peak_db, sine, stereo
from utils.analyzer import compute_lufs, compute_rms

CEILING_TOLERANCE_DB = 0.01


class TestLimit:
    def test_peak_never_exceeds_ceiling(self, sample_rate):
        loud = sine(440.0, 2.0, amplitude=1.0)
        limited = limit(loud, sample_rate, ceiling_db=-1.0)
        assert peak_db(limited) <= -1.0 + CEILING_TOLERANCE_DB

    def test_custom_ceiling_is_respected(self, sample_rate):
        loud = sine(440.0, 2.0, amplitude=1.0)
        limited = limit(loud, sample_rate, ceiling_db=-6.0)
        assert peak_db(limited) <= -6.0 + CEILING_TOLERANCE_DB

    def test_quiet_signal_gets_no_makeup_gain(self, sample_rate):
        """회귀 방지: pedalboard.Limiter는 조용한 신호를 ~5dB 키워버렸다."""
        quiet = sine(440.0, 2.0, amplitude=0.05)  # 약 -26dBFS
        limited = limit(quiet, sample_rate, ceiling_db=-1.0)
        assert peak_db(limited) == pytest.approx(peak_db(quiet), abs=0.01)

    def test_signal_below_ceiling_is_left_alone(self, sample_rate):
        # -3dBFS 신호는 -1dBFS ceiling 아래라 건드리지 않아야 한다.
        signal = sine(440.0, 2.0, amplitude=0.7)
        limited = limit(signal, sample_rate, ceiling_db=-1.0)
        np.testing.assert_allclose(limited, signal, atol=1e-6)

    def test_no_overshoot_just_below_ceiling(self, sample_rate):
        """회귀 방지: -0.4dB 신호가 0dBFS로 튀어나오던 문제."""
        signal = sine(440.0, 2.0, amplitude=10.0 ** (-0.4 / 20.0))
        limited = limit(signal, sample_rate, ceiling_db=-1.0)
        assert peak_db(limited) <= -1.0 + CEILING_TOLERANCE_DB

    def test_stereo_gain_is_channel_linked(self, sample_rate):
        """좌우 게인을 따로 계산하면 스테레오 이미지가 흔들린다 → 비율 유지 확인."""
        left = sine(440.0, 2.0, amplitude=1.0)
        right = sine(440.0, 2.0, amplitude=0.5)  # 오른쪽이 6dB 작음
        signal = stereo(left, right)

        limited = limit(signal, sample_rate, ceiling_db=-1.0)

        assert limited.shape == signal.shape
        before = compute_rms(signal[:, 0]) / compute_rms(signal[:, 1])
        after = compute_rms(limited[:, 0]) / compute_rms(limited[:, 1])
        assert after == pytest.approx(before, rel=1e-4)
        assert peak_db(limited) <= -1.0 + CEILING_TOLERANCE_DB

    def test_transient_peak_is_tamed(self, sample_rate):
        # 조용한 신호 한가운데 순간적인 큰 피크가 있는 경우.
        signal = sine(440.0, 2.0, amplitude=0.1)
        signal[sample_rate] = 0.99
        limited = limit(signal, sample_rate, ceiling_db=-1.0)
        assert peak_db(limited) <= -1.0 + CEILING_TOLERANCE_DB

    def test_empty_returns_empty(self, sample_rate):
        assert limit(np.array([], dtype=np.float32), sample_rate).size == 0

    def test_output_is_float32(self, sample_rate):
        assert limit(sine(440.0, 1.0), sample_rate).dtype == np.float32


class TestMaster:
    def test_reaches_target_lufs(self, sample_rate):
        quiet = sine(1000.0, 5.0, amplitude=0.05)
        mastered = master(quiet, sample_rate, target_lufs=-14.0)
        assert compute_lufs(mastered, sample_rate) == pytest.approx(-14.0, abs=0.5)

    def test_turns_down_a_too_loud_signal(self, sample_rate):
        loud = sine(1000.0, 5.0, amplitude=0.9)
        mastered = master(loud, sample_rate, target_lufs=-14.0)
        assert compute_lufs(mastered, sample_rate) == pytest.approx(-14.0, abs=0.5)

    def test_custom_target_lufs(self, sample_rate):
        signal = sine(1000.0, 5.0, amplitude=0.2)
        mastered = master(signal, sample_rate, target_lufs=-20.0)
        assert compute_lufs(mastered, sample_rate) == pytest.approx(-20.0, abs=0.5)

    def test_peak_stays_under_ceiling(self, sample_rate):
        signal = sine(1000.0, 5.0, amplitude=0.05)
        mastered = master(signal, sample_rate, target_lufs=-14.0, ceiling_db=-1.0)
        assert peak_db(mastered) <= -1.0 + CEILING_TOLERANCE_DB

    def test_stereo_is_preserved(self, sample_rate):
        mono = sine(1000.0, 5.0, amplitude=0.1)
        mastered = master(stereo(mono, mono * 0.5), sample_rate)
        assert mastered.ndim == 2 and mastered.shape[1] == 2
        assert compute_lufs(mastered, sample_rate) == pytest.approx(-14.0, abs=0.5)

    def test_silence_is_returned_unchanged(self, sample_rate):
        silence = np.zeros(sample_rate, dtype=np.float32)
        np.testing.assert_array_equal(master(silence, sample_rate), silence)

    def test_empty_returns_empty(self, sample_rate):
        assert master(np.array([], dtype=np.float32), sample_rate).size == 0

    def test_very_short_audio_falls_back_to_limiting(self, sample_rate):
        """LUFS 측정 불가(0.4초 미만)여도 예외 없이 리미터만 적용돼야 한다."""
        short = sine(1000.0, 0.05, amplitude=1.0)
        mastered = master(short, sample_rate, ceiling_db=-1.0)
        assert mastered.shape == short.shape
        assert peak_db(mastered) <= -1.0 + CEILING_TOLERANCE_DB
