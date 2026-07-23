"""pipeline/balance.py — 구간별 RMS 매칭 + 게인 보간 테스트."""

import numpy as np
import pytest

from pipeline.balance import balance_levels
from tests.conftest import sine, stereo
from utils.analyzer import compute_rms


def rms_difference_db(track: np.ndarray, reference: np.ndarray) -> float:
    """track이 reference보다 몇 dB 위인지 계산한다."""
    return 20.0 * np.log10(compute_rms(track) / compute_rms(reference))


class TestBalanceLevels:
    def test_zero_offset_matches_reference_level(self, sample_rate):
        # 필요한 게인이 ±12dB 클램프 안에 들어오도록 레벨 차이를 8dB 정도로 둔다.
        track = sine(440.0, 3.0, amplitude=0.2)
        reference = sine(220.0, 3.0, amplitude=0.5)
        balanced = balance_levels(track, reference, sample_rate, offset_db=0.0)
        assert rms_difference_db(balanced, reference) == pytest.approx(0.0, abs=0.1)

    def test_positive_offset_lifts_track_above_reference(self, sample_rate):
        # mix 모드의 보컬 +3dB 규칙.
        track = sine(440.0, 3.0, amplitude=0.2)
        reference = sine(220.0, 3.0, amplitude=0.2)
        balanced = balance_levels(track, reference, sample_rate, offset_db=3.0)
        assert rms_difference_db(balanced, reference) == pytest.approx(3.0, abs=0.1)

    def test_negative_offset_pushes_track_below_reference(self, sample_rate):
        # stems 모드의 베이스 -2dB 같은 경우.
        track = sine(440.0, 3.0, amplitude=0.2)
        reference = sine(220.0, 3.0, amplitude=0.2)
        balanced = balance_levels(track, reference, sample_rate, offset_db=-2.0)
        assert rms_difference_db(balanced, reference) == pytest.approx(-2.0, abs=0.1)

    def test_gain_is_clamped_to_plus_12db(self, sample_rate):
        # 트랙이 기준보다 40dB 낮아도 최대 +12dB까지만 올린다.
        track = sine(440.0, 3.0, amplitude=0.005)
        reference = sine(220.0, 3.0, amplitude=0.5)
        balanced = balance_levels(track, reference, sample_rate, offset_db=0.0)
        applied_db = 20.0 * np.log10(compute_rms(balanced) / compute_rms(track))
        assert applied_db == pytest.approx(12.0, abs=0.1)

    def test_gain_is_clamped_to_minus_12db(self, sample_rate):
        track = sine(440.0, 3.0, amplitude=0.5)
        reference = sine(220.0, 3.0, amplitude=0.005)
        balanced = balance_levels(track, reference, sample_rate, offset_db=0.0)
        applied_db = 20.0 * np.log10(compute_rms(balanced) / compute_rms(track))
        assert applied_db == pytest.approx(-12.0, abs=0.1)

    def test_gain_curve_has_no_sudden_steps(self, sample_rate):
        """계단식 게인은 지퍼 노이즈를 만든다 → 보간된 곡선인지 확인."""
        # 앞 절반은 작고 뒤 절반은 큰 기준 트랙 → 게인이 크게 변해야 하는 상황.
        quiet = sine(220.0, 2.0, amplitude=0.05)
        loud = sine(220.0, 2.0, amplitude=0.5)
        reference = np.concatenate([quiet, loud])
        track = sine(440.0, 4.0, amplitude=0.2)

        balanced = balance_levels(track, reference, sample_rate, offset_db=0.0)
        # 사인파가 0을 지나는 지점은 나눗셈이 불안정하므로 충분히 큰 샘플만 본다.
        stable = np.abs(track) > 0.05
        applied_gain = balanced[stable].astype(np.float64) / track[stable].astype(np.float64)
        gain_steps = np.abs(np.diff(applied_gain))
        assert np.max(gain_steps) < 0.01, "게인이 한 샘플에서 급격히 점프했습니다."

    def test_stereo_keeps_shape_and_image(self, sample_rate):
        """좌우에 같은 게인 곡선을 적용해야 스테레오 이미지가 유지된다."""
        left = sine(440.0, 3.0, amplitude=0.2)
        right = sine(440.0, 3.0, amplitude=0.1)  # 오른쪽이 6dB 작은 상태
        track = stereo(left, right)
        reference = stereo(sine(220.0, 3.0, 0.4), sine(220.0, 3.0, 0.4))

        balanced = balance_levels(track, reference, sample_rate, offset_db=0.0)

        assert balanced.shape == track.shape
        before = compute_rms(track[:, 0]) / compute_rms(track[:, 1])
        after = compute_rms(balanced[:, 0]) / compute_rms(balanced[:, 1])
        assert after == pytest.approx(before, rel=1e-4)

    def test_silent_track_is_returned_unchanged(self, sample_rate):
        # 무음 구간만 있으면 계산할 게인이 없어 원본을 그대로 돌려준다.
        track = np.zeros(sample_rate * 2, dtype=np.float32)
        reference = sine(220.0, 2.0, amplitude=0.5)
        balanced = balance_levels(track, reference, sample_rate)
        np.testing.assert_array_equal(balanced, track)

    def test_empty_track_returns_empty(self, sample_rate):
        empty = np.array([], dtype=np.float32)
        assert balance_levels(empty, sine(220.0, 1.0), sample_rate).size == 0

    def test_empty_reference_returns_track_unchanged(self, sample_rate):
        track = sine(440.0, 1.0, amplitude=0.2)
        empty = np.array([], dtype=np.float32)
        np.testing.assert_array_equal(balance_levels(track, empty, sample_rate), track)

    def test_output_is_float32(self, sample_rate):
        track = sine(440.0, 2.0, amplitude=0.2)
        reference = sine(220.0, 2.0, amplitude=0.3)
        assert balance_levels(track, reference, sample_rate).dtype == np.float32

    def test_invalid_segment_seconds_raises(self, sample_rate):
        track = sine(440.0, 1.0)
        with pytest.raises(ValueError):
            balance_levels(track, track, sample_rate, segment_seconds=0.0)

    def test_shorter_reference_still_works(self, sample_rate):
        # 기준 트랙이 더 짧아도 인덱스 오류 없이 처리돼야 한다.
        track = sine(440.0, 4.0, amplitude=0.2)
        reference = sine(220.0, 1.5, amplitude=0.2)
        balanced = balance_levels(track, reference, sample_rate)
        assert balanced.shape == track.shape
        assert np.all(np.isfinite(balanced))
