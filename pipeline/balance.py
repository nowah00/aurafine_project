"""보컬/MR 레벨 밸런싱 (구간별 RMS 매칭)."""

import numpy as np

from utils.analyzer import compute_rms


def balance_levels(
    vocal: np.ndarray, mr: np.ndarray, sample_rate: int, segment_seconds: float = 1.0
) -> np.ndarray:
    """1초 구간별 RMS를 비교해 보컬 레벨을 MR에 맞춘다.

    한 구간의 변화량은 ±12dB로 제한해, 조용한 구간에서 과도하게 증폭되는 것을 막는다.
    """
    if vocal.size == 0 or mr.size == 0:
        return vocal.copy()
    if segment_seconds <= 0:
        raise ValueError("segment_seconds는 0보다 커야 합니다.")

    segment_size = max(1, int(sample_rate * segment_seconds))
    balanced = vocal.astype(np.float32, copy=True)

    for start in range(0, vocal.size, segment_size):
        end = min(start + segment_size, vocal.size, mr.size)
        if end <= start:
            break

        vocal_rms = compute_rms(vocal[start:end])
        mr_rms = compute_rms(mr[start:end])
        if vocal_rms < 1e-5 or mr_rms < 1e-5:
            continue

        gain_db = 20.0 * np.log10(mr_rms / vocal_rms)
        safe_gain_db = float(np.clip(gain_db, -12.0, 12.0))
        balanced[start:end] *= 10.0 ** (safe_gain_db / 20.0)

    return balanced
