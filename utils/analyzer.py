"""오디오 분석에 재사용하는 작은 헬퍼 함수들."""

import librosa
import numpy as np
import pyloudnorm as pyln


def compute_rms(audio: np.ndarray) -> float:
    """오디오 신호의 RMS(평균적인 에너지)를 반환한다."""
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))


def compute_lufs(audio: np.ndarray, sample_rate: int) -> float:
    """pyloudnorm으로 통합 라우드니스(LUFS)를 측정한다."""
    if audio.size == 0 or compute_rms(audio) == 0.0:
        return float("-inf")

    meter = pyln.Meter(sample_rate)
    return float(meter.integrated_loudness(audio))


def find_resonant_peaks(
    audio: np.ndarray, sample_rate: int, max_peaks: int = 3
) -> list[float]:
    """200~8000Hz에서 두드러지는 공명 피크 주파수를 찾아 반환한다."""
    if audio.size == 0:
        return []

    spectrum = np.mean(np.abs(librosa.stft(audio)), axis=1)
    frequencies = librosa.fft_frequencies(sr=sample_rate)
    in_voice_range = (frequencies >= 200) & (frequencies <= 8000)
    candidate_indexes = np.where(in_voice_range)[0]

    # 양옆보다 큰 지점만 골라 넓은 대역의 평균적인 에너지와 구별한다.
    local_maxima = [
        index
        for index in candidate_indexes[1:-1]
        if spectrum[index] > spectrum[index - 1]
        and spectrum[index] > spectrum[index + 1]
    ]
    if not local_maxima:
        return []

    strongest = sorted(local_maxima, key=lambda index: spectrum[index], reverse=True)
    return [float(frequencies[index]) for index in strongest[:max_peaks]]
