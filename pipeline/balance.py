"""트랙 레벨 밸런싱 (구간별 RMS 매칭 + 부드러운 게인 보간).

보컬-MR 밸런싱(mix 모드)과 스템 간 밸런싱(stems 모드, pipeline/stems.py)이
모두 이 함수 하나를 재사용한다.
"""

import numpy as np

from utils.analyzer import compute_rms


def balance_levels(
    track: np.ndarray,
    reference: np.ndarray,
    sample_rate: int,
    segment_seconds: float = 1.0,
    offset_db: float = 3.0,
) -> np.ndarray:
    """1초 구간별 RMS를 비교해 track 레벨을 reference 대비 offset_db로 맞춘다.

    - offset_db: 예) 보컬은 MR보다 +3dB 위로, 베이스는 드럼보다 -2dB 아래로.
    - 구간별 게인을 계단식으로 곱하면 경계에서 딸깍거리는 잡음이 생기므로,
      구간 중심점 사이를 선형 보간(np.interp)해 샘플마다 부드럽게 변하는
      게인 곡선을 만들어 적용한다.
    """
    if track.size == 0 or reference.size == 0:
        return track.astype(np.float32, copy=True)
    if segment_seconds <= 0:
        raise ValueError("segment_seconds는 0보다 커야 합니다.")

    # 모노는 1차원 (N,), 스테레오는 2차원 (N, 채널). 길이는 항상 첫 축(프레임 수)이다.
    track_length = track.shape[0]
    reference_length = reference.shape[0]
    segment_size = max(1, int(sample_rate * segment_seconds))
    centers: list[float] = []
    gains_db: list[float] = []

    for start in range(0, track_length, segment_size):
        end = min(start + segment_size, track_length, reference_length)
        if end <= start:
            break

        track_rms = compute_rms(track[start:end])
        reference_rms = compute_rms(reference[start:end])
        # 무음에 가까운 구간은 건너뛴다. (보간이 이웃 구간 값으로 메워준다)
        if track_rms < 1e-5 or reference_rms < 1e-5:
            continue

        gain_db = 20.0 * np.log10(reference_rms / track_rms) + offset_db
        centers.append((start + end) / 2.0)
        gains_db.append(float(np.clip(gain_db, -12.0, 12.0)))

    if not centers:
        return track.astype(np.float32, copy=True)

    # 모든 샘플 위치에 대해 게인(dB)을 보간한 뒤 배율로 변환해 곱한다.
    positions = np.arange(track_length, dtype=np.float64)
    gain_curve_db = np.interp(positions, centers, gains_db)
    gain_curve = 10.0 ** (gain_curve_db / 20.0)
    if track.ndim == 2:
        # 스테레오는 같은 게인 곡선을 두 채널에 동일하게 곱한다. (이미지 유지)
        gain_curve = gain_curve[:, None]

    return (track.astype(np.float64) * gain_curve).astype(np.float32)
