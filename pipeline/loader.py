"""ffmpeg와 librosa를 이용한 오디오 로딩 및 형식 정규화.

채널 규약: 모노는 1차원 배열 (N,), 스테레오는 2차원 배열 (N, 2)로 다룬다.
(soundfile의 저장 규약과 같은 '샘플 우선' 배치.) 다운스트림 DSP 모듈은
이 두 형태를 모두 받는다.
"""

from pathlib import Path
import subprocess
import tempfile

import librosa
import numpy as np


def load_and_normalize(
    path: str | Path, sample_rate: int = 44100, mono: bool = False
) -> tuple[np.ndarray, int]:
    """입력 파일을 44.1kHz/24-bit WAV로 정규화해 반환한다.

    - mono=True: 항상 모노(1차원)로 다운믹스한다. (보컬 체인용)
    - mono=False: 입력의 채널 수를 보존한다. 모노 입력은 1차원, 스테레오
      입력은 (N, 2) 2차원으로 반환한다. 3채널 이상은 앞의 2채널만 쓴다.
    """
    input_path = Path(path).expanduser()
    if not input_path.is_file():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {input_path}")

    with tempfile.TemporaryDirectory(prefix="aurafine_") as temporary_dir:
        normalized_path = Path(temporary_dir) / "normalized.wav"
        command = ["ffmpeg", "-y", "-i", str(input_path), "-ar", str(sample_rate)]
        if mono:
            command += ["-ac", "1"]  # 모노 강제 (그 외에는 입력 채널을 그대로 둔다)
        command += ["-c:a", "pcm_s24le", str(normalized_path)]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("ffmpeg가 없습니다. 설치 후 다시 실행하세요.") from error
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip().splitlines()[-1] if error.stderr else "알 수 없는 오류"
            raise RuntimeError(f"오디오 변환에 실패했습니다: {message}") from error

        # mono=False로 읽으면 모노 파일은 (N,), 다채널 파일은 (채널, N)로 온다.
        audio, loaded_rate = librosa.load(normalized_path, sr=sample_rate, mono=mono)

    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 2:
        # librosa는 (채널, N) 순서라 (N, 채널)로 뒤집고, 3채널 이상은 2채널로 줄인다.
        audio = audio.T[:, :2]
    return audio, int(loaded_rate)


def pad_to_length(audio: np.ndarray, length: int) -> np.ndarray:
    """시간 축(첫 축) 뒤만 무음으로 채워 프레임 수를 length로 맞춘다. (모노/스테레오 공용)"""
    pad_frames = length - audio.shape[0]
    if audio.ndim == 1:
        return np.pad(audio, (0, pad_frames))
    return np.pad(audio, ((0, pad_frames), (0, 0)))


def to_stereo(audio: np.ndarray) -> np.ndarray:
    """모노(1차원)를 좌우 동일한 스테레오(N, 2)로 업믹스한다. 이미 스테레오면 그대로."""
    if audio.ndim == 2:
        return audio
    return np.column_stack([audio, audio])


def match_channels(*tracks: np.ndarray) -> tuple[np.ndarray, ...]:
    """트랙 중 하나라도 스테레오면 나머지 모노를 스테레오로 맞춘다. (믹스 전 채널 정렬)"""
    if any(track.ndim == 2 for track in tracks):
        return tuple(to_stereo(track) for track in tracks)
    return tracks
