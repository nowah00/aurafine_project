"""pipeline/stems.py — 목표 레벨 테이블, 앵커 선택, 스템 밸런싱 테스트."""

import numpy as np
import pytest

from pipeline import stems
from pipeline.stems import STEM_TARGET_LEVELS_DB, balance_stems
from tests.conftest import sine, stereo
from utils.analyzer import compute_rms

ALL_STEMS = {"drum", "bass", "electric_guitar", "acoustic_guitar", "piano", "vocal"}


def level_difference_db(first: np.ndarray, second: np.ndarray) -> float:
    """first가 second보다 몇 dB 위인지."""
    return 20.0 * np.log10(compute_rms(first) / compute_rms(second))


@pytest.fixture
def three_tracks():
    """레벨이 조금씩 다른 드럼/베이스/피아노 트랙 (밸런싱 대상).

    어느 트랙이 anchor가 되든 필요한 게인이 ±12dB 클램프 안에 들어오도록
    트랙 간 레벨 차이를 작게 잡았다. (클램프가 걸리면 목표 오프셋에 못 미친다)
    """
    return {
        "drum": sine(100.0, 3.0, amplitude=0.30),
        "bass": sine(80.0, 3.0, amplitude=0.25),
        "piano": sine(440.0, 3.0, amplitude=0.20),
    }


class TestTargetLevels:
    def test_table_covers_every_supported_stem(self):
        assert set(STEM_TARGET_LEVELS_DB) == ALL_STEMS

    def test_drum_is_the_zero_reference(self):
        assert STEM_TARGET_LEVELS_DB["drum"] == 0.0

    def test_vocal_reuses_the_plus_3db_convention(self):
        # mix 모드에서 보컬이 MR보다 +3dB 위인 것과 같은 값.
        assert STEM_TARGET_LEVELS_DB["vocal"] == 3.0


class TestBalanceStems:
    def test_anchor_is_never_touched(self, three_tracks, sample_rate):
        balanced = balance_stems(three_tracks, "drum", sample_rate)
        np.testing.assert_array_equal(balanced["drum"], three_tracks["drum"])

    def test_all_tracks_are_returned(self, three_tracks, sample_rate):
        balanced = balance_stems(three_tracks, "drum", sample_rate)
        assert set(balanced) == set(three_tracks)

    def test_offsets_follow_the_target_table(self, three_tracks, sample_rate):
        balanced = balance_stems(three_tracks, "drum", sample_rate)
        # 베이스는 드럼보다 -2dB, 피아노는 -5dB.
        assert level_difference_db(balanced["bass"], balanced["drum"]) == pytest.approx(
            -2.0, abs=0.1
        )
        assert level_difference_db(balanced["piano"], balanced["drum"]) == pytest.approx(
            -5.0, abs=0.1
        )

    def test_relative_balance_is_identical_whichever_track_is_anchor(
        self, three_tracks, sample_rate
    ):
        """회귀 방지의 핵심: 앵커가 바뀌어도 트랙 간 상대 밸런스는 같아야 한다."""
        by_drum = balance_stems(three_tracks, "drum", sample_rate)
        by_bass = balance_stems(three_tracks, "bass", sample_rate)
        by_piano = balance_stems(three_tracks, "piano", sample_rate)

        for pair in [("bass", "drum"), ("piano", "drum"), ("piano", "bass")]:
            first, second = pair
            expected = STEM_TARGET_LEVELS_DB[first] - STEM_TARGET_LEVELS_DB[second]
            for balanced in (by_drum, by_bass, by_piano):
                actual = level_difference_db(balanced[first], balanced[second])
                assert actual == pytest.approx(expected, abs=0.1), f"{pair} 불일치"

    def test_two_tracks_is_enough(self, sample_rate):
        tracks = {
            "bass": sine(80.0, 3.0, amplitude=0.30),
            "vocal": sine(440.0, 3.0, amplitude=0.25),
        }
        balanced = balance_stems(tracks, "bass", sample_rate)
        # 보컬(+3) - 베이스(-2) = +5dB
        assert level_difference_db(balanced["vocal"], balanced["bass"]) == pytest.approx(
            5.0, abs=0.1
        )

    def test_stereo_tracks_keep_their_shape(self, sample_rate):
        mono = sine(100.0, 3.0, amplitude=0.3)
        tracks = {
            "drum": stereo(mono, mono * 0.8),
            "piano": stereo(sine(440.0, 3.0, 0.1), sine(440.0, 3.0, 0.2)),
        }
        balanced = balance_stems(tracks, "drum", sample_rate)
        for name, audio in balanced.items():
            assert audio.shape == tracks[name].shape

    def test_anchor_copy_does_not_alias_the_input(self, three_tracks, sample_rate):
        # 앵커는 복사본이어야 원본 배열이 나중에 변조되지 않는다.
        balanced = balance_stems(three_tracks, "drum", sample_rate)
        assert balanced["drum"] is not three_tracks["drum"]


class TestPickAnchor:
    def test_first_flag_on_the_command_line_wins(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["main.py", "--mode", "stems", "--piano", "p.wav", "--drum", "d.wav"],
        )
        tracks = {"drum": "d.wav", "piano": "p.wav"}
        assert stems._pick_anchor(tracks) == "piano"

    def test_handles_equals_style_flags(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--bass=b.wav", "--drum=d.wav"])
        tracks = {"drum": "d.wav", "bass": "b.wav"}
        assert stems._pick_anchor(tracks) == "bass"

    def test_kebab_case_flags_map_to_snake_case_names(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv", ["main.py", "--electric-guitar", "e.wav", "--drum", "d.wav"]
        )
        tracks = {"drum": "d.wav", "electric_guitar": "e.wav"}
        assert stems._pick_anchor(tracks) == "electric_guitar"

    def test_ignores_flags_for_tracks_that_were_not_provided(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--vocal", "v.wav", "--drum", "d.wav"])
        tracks = {"drum": "d.wav"}  # vocal은 넘기지 않은 상황
        assert stems._pick_anchor(tracks) == "drum"

    def test_falls_back_to_first_dict_entry(self, monkeypatch):
        # 코드에서 직접 호출해 sys.argv에 플래그가 없을 때의 대비책.
        monkeypatch.setattr("sys.argv", ["pytest"])
        tracks = {"piano": "p.wav", "drum": "d.wav"}
        assert stems._pick_anchor(tracks) == "piano"
