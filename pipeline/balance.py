"""보컬/MR 레벨 밸런싱 (구간별 RMS 매칭 + 부드러운 게인 보간)."""

import numpy as np

from utils.analyzer import compute_rms


def balance_levels(
    vocal: np.ndarray,
    mr: np.ndarray,
    sample_rate: int,
    segment_seconds: float = 1.0,
    vocal_offset_db: float = 3.0,
) -> np.ndarray:
    """1초 구간별 RMS를 비교해 보컬 레벨을 MR에 맞춘다.

    - vocal_offset_db: 보컬이 MR에 묻히지 않도록 기본 +3dB 위에 얹는다.
    - 구간별 게인을 계단식으로 곱하면 경계에서 딸깍거리는 잡음이 생기므로,
      구간 중심점 사이를 선형 보간(np.interp)해 샘플마다 부드럽게 변하는
      게인 곡선을 만들어 적용한다.
    """
    if vocal.size == 0 or mr.size == 0:
        return vocal.astype(np.float32, copy=True)
    if segment_seconds <= 0:
        raise ValueError("segment_seconds는 0보다 커야 합니다.")

    segment_size = max(1, int(sample_rate * segment_seconds))
    centers: list[float] = []
    gains_db: list[float] = []

    for start in range(0, vocal.size, segment_size):
        end = min(start + segment_size, vocal.size, mr.size)
        if end <= start:
            break

        vocal_rms = compute_rms(vocal[start:end])
        mr_rms = compute_rms(mr[start:end])
        # 무음에 가까운 구간은 건너뛴다. (보간이 이웃 구간 값으로 메워준다)
        if vocal_rms < 1e-5 or mr_rms < 1e-5:
            continue

        gain_db = 20.0 * np.log10(mr_rms / vocal_rms) + vocal_offset_db
        centers.append((start + end) / 2.0)
        gains_db.append(float(np.clip(gain_db, -12.0, 12.0)))

    if not centers:
        return vocal.astype(np.float32, copy=True)

    # 모든 샘플 위치에 대해 게인(dB)을 보간한 뒤 배율로 변환해 곱한다.
    positions = np.arange(vocal.size, dtype=np.float64)
    gain_curve_db = np.interp(positions, centers, gains_db)
    gain_curve = 10.0 ** (gain_curve_db / 20.0)

    return (vocal.astype(np.float64) * gain_curve).astype(np.float32)
