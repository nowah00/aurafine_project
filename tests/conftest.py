"""테스트 공용 설정과 신호 생성 헬퍼.

실제 음원 파일 없이도 돌도록, 모든 테스트는 여기서 만든 합성 신호를 쓴다.
"""

import numpy as np
import pytest

SAMPLE_RATE = 44100


@pytest.fixture
def sample_rate() -> int:
    """모든 테스트가 공유하는 샘플레이트(파이프라인 표준값 44.1kHz)."""
    return SAMPLE_RATE


def sine(
    frequency: float,
    seconds: float,
    amplitude: float = 0.5,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """진폭이 일정한 사인파 모노 신호 (N,)를 만든다."""
    time = np.arange(int(sample_rate * seconds), dtype=np.float64) / sample_rate
    return (amplitude * np.sin(2.0 * np.pi * frequency * time)).astype(np.float32)


def stereo(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """모노 두 개를 (N, 2) 스테레오로 합친다."""
    return np.column_stack([left, right]).astype(np.float32)


def peak_db(audio: np.ndarray) -> float:
    """최대 절댓값을 dBFS로 반환한다."""
    return 20.0 * np.log10(max(float(np.max(np.abs(audio))), 1e-12))


def band_energy(
    audio: np.ndarray, low: float, high: float, sample_rate: int = SAMPLE_RATE
) -> float:
    """FFT로 low~high Hz 구간의 에너지 총합을 구한다. (필터 효과 검증용)"""
    spectrum = np.abs(np.fft.rfft(audio.astype(np.float64)))
    frequencies = np.fft.rfftfreq(audio.shape[0], d=1.0 / sample_rate)
    in_band = (frequencies >= low) & (frequencies <= high)
    return float(np.sum(np.square(spectrum[in_band])))
