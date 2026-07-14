"""ffmpeg와 librosa를 이용한 오디오 로딩 및 형식 정규화."""

from pathlib import Path
import subprocess
import tempfile

import librosa
import numpy as np


def load_and_normalize(path: str | Path, sample_rate: int = 44100) -> tuple[np.ndarray, int]:
    """입력 파일을 44.1kHz/24-bit/모노 WAV로 정규화해 반환한다."""
    input_path = Path(path).expanduser()
    if not input_path.is_file():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {input_path}")

    with tempfile.TemporaryDirectory(prefix="aurafine_") as temporary_dir:
        normalized_path = Path(temporary_dir) / "normalized.wav"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s24le",
            str(normalized_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("ffmpeg가 없습니다. 설치 후 다시 실행하세요.") from error
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip().splitlines()[-1] if error.stderr else "알 수 없는 오류"
            raise RuntimeError(f"오디오 변환에 실패했습니다: {message}") from error

        # mono=True로 읽으면 이후 DSP 모듈이 항상 1차원 배열을 받는다.
        audio, loaded_rate = librosa.load(normalized_path, sr=sample_rate, mono=True)

    return np.asarray(audio, dtype=np.float32), int(loaded_rate)
