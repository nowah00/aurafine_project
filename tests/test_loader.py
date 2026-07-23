"""pipeline/loader.py — 로딩/정규화와 채널 정렬 헬퍼 테스트.

load_and_normalize는 ffmpeg를 실제로 실행하므로 `ffmpeg` 마커를 달았다.
(ffmpeg가 없는 환경에서는 자동으로 건너뛴다.)
"""

import shutil

import numpy as np
import pytest
import soundfile as sf

from pipeline.loader import load_and_normalize, match_channels, pad_to_length, to_stereo
from tests.conftest import sine, stereo

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg가 PATH에 없습니다."
)


@pytest.fixture
def write_wav(tmp_path):
    """테스트용 WAV 파일을 만들어 경로를 돌려주는 헬퍼."""

    def _write(name: str, audio: np.ndarray, sample_rate: int = 48000):
        path = tmp_path / name
        sf.write(path, audio, sample_rate)
        return path

    return _write


class TestPadToLength:
    def test_pads_mono_with_silence(self):
        padded = pad_to_length(np.ones(100, dtype=np.float32), 150)
        assert padded.shape == (150,)
        assert np.all(padded[100:] == 0.0)

    def test_pads_stereo_on_the_frame_axis_only(self):
        """회귀 방지: size 기반 계산은 채널×프레임을 세어 스테레오에서 깨진다."""
        audio = np.ones((100, 2), dtype=np.float32)
        padded = pad_to_length(audio, 150)
        assert padded.shape == (150, 2)
        assert np.all(padded[100:, :] == 0.0)

    def test_same_length_is_a_no_op(self):
        audio = np.ones((100, 2), dtype=np.float32)
        np.testing.assert_array_equal(pad_to_length(audio, 100), audio)


class TestToStereo:
    def test_mono_becomes_dual_mono(self):
        mono = sine(440.0, 0.1)
        upmixed = to_stereo(mono)
        assert upmixed.shape == (mono.shape[0], 2)
        np.testing.assert_array_equal(upmixed[:, 0], upmixed[:, 1])

    def test_stereo_passes_through(self):
        audio = stereo(sine(440.0, 0.1), sine(880.0, 0.1))
        assert to_stereo(audio) is audio


class TestMatchChannels:
    def test_mono_is_upmixed_when_any_track_is_stereo(self):
        mono = sine(440.0, 0.1)
        stereo_track = stereo(mono, mono * 0.5)
        matched = match_channels(mono, stereo_track)
        assert all(track.ndim == 2 for track in matched)
        assert matched[0].shape == matched[1].shape

    def test_all_mono_stays_mono(self):
        first, second = sine(440.0, 0.1), sine(880.0, 0.1)
        matched = match_channels(first, second)
        assert all(track.ndim == 1 for track in matched)


@needs_ffmpeg
@pytest.mark.ffmpeg
class TestLoadAndNormalize:
    def test_resamples_to_44100(self, write_wav):
        path = write_wav("mono48k.wav", sine(440.0, 0.5, sample_rate=48000), 48000)
        audio, sample_rate = load_and_normalize(path)
        assert sample_rate == 44100
        assert audio.shape[0] == pytest.approx(44100 * 0.5, rel=0.02)

    def test_mono_file_stays_one_dimensional(self, write_wav):
        path = write_wav("mono.wav", sine(440.0, 0.5, sample_rate=48000), 48000)
        audio, _ = load_and_normalize(path)
        assert audio.ndim == 1

    def test_stereo_file_becomes_frames_by_two(self, write_wav):
        left = sine(440.0, 0.5, amplitude=0.5, sample_rate=48000)
        right = sine(880.0, 0.5, amplitude=0.2, sample_rate=48000)
        path = write_wav("stereo.wav", stereo(left, right), 48000)

        audio, _ = load_and_normalize(path)

        assert audio.ndim == 2 and audio.shape[1] == 2
        # 좌우가 다른 신호로 유지되는지(이미지 보존) 확인.
        assert not np.allclose(audio[:, 0], audio[:, 1])

    def test_mono_flag_downmixes_stereo(self, write_wav):
        left = sine(440.0, 0.5, sample_rate=48000)
        right = sine(880.0, 0.5, sample_rate=48000)
        path = write_wav("stereo2.wav", stereo(left, right), 48000)

        audio, _ = load_and_normalize(path, mono=True)

        assert audio.ndim == 1

    def test_more_than_two_channels_is_truncated(self, write_wav):
        frames = sine(440.0, 0.5, sample_rate=48000).shape[0]
        four_channel = np.tile(sine(440.0, 0.5, sample_rate=48000)[:, None], (1, 4))
        assert four_channel.shape == (frames, 4)
        path = write_wav("quad.wav", four_channel, 48000)

        audio, _ = load_and_normalize(path)

        assert audio.ndim == 2 and audio.shape[1] == 2

    def test_output_is_float32(self, write_wav):
        path = write_wav("mono2.wav", sine(440.0, 0.3, sample_rate=48000), 48000)
        audio, _ = load_and_normalize(path)
        assert audio.dtype == np.float32

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_and_normalize(tmp_path / "없는파일.wav")
