"""마스터링: -14 LUFS 정규화 + -1dBFS 브릭월 리미팅.

pedalboard의 Limiter는 자동 메이크업 게인이 있어 조용한 신호를 키우고
ceiling도 정확히 지키지 않아, 여기서는 직접 구현한 리미터를 사용한다.
"""

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d

from utils.analyzer import compute_lufs, compute_rms


def limit(audio: np.ndarray, sample_rate: int, ceiling_db: float = -1.0) -> np.ndarray:
    """피크가 ceiling_db를 절대 넘지 않게 게인을 순간적으로 줄이는 브릭월 리미터.

    동작 원리: 샘플마다 "ceiling을 지키는 데 필요한 게인"을 구한 뒤,
    (1) 룩어헤드 최소값 필터로 피크보다 한발 먼저 게인을 내리고
    (2) 이동 평균으로 게인 변화를 부드럽게 만들어 딸깍임을 없앤다.
    """
    if audio.size == 0:
        return audio.astype(np.float32, copy=True)

    ceiling = 10.0 ** (ceiling_db / 20.0)
    # 스테레오는 두 채널 중 큰 피크를 기준으로 게인을 계산해 양 채널에 동일하게
    # 적용한다. (채널별로 따로 줄이면 좌우 밸런스가 틀어져 이미지가 흔들린다.)
    abs_audio = np.abs(audio.astype(np.float64))
    peak = abs_audio.max(axis=1) if audio.ndim == 2 else abs_audio
    needed_gain = np.minimum(1.0, ceiling / (peak + 1e-12))

    lookahead = max(1, int(sample_rate * 0.006))  # 6ms 앞서 반응
    smooth_window = max(1, int(sample_rate * 0.003))  # 3ms에 걸쳐 부드럽게
    gain = minimum_filter1d(needed_gain, size=lookahead)
    gain = uniform_filter1d(gain, size=smooth_window)
    if audio.ndim == 2:
        gain = gain[:, None]  # (N,) 게인을 두 채널에 브로드캐스트

    limited = audio.astype(np.float64) * gain
    # 스무딩으로 생길 수 있는 미세한 초과분(0.1dB 미만)을 마지막에 잘라낸다.
    return np.clip(limited, -ceiling, ceiling).astype(np.float32)


def master(
    audio: np.ndarray,
    sample_rate: int,
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
) -> np.ndarray:
    """목표 LUFS로 라우드니스를 맞춘 뒤, 리미터로 피크를 ceiling 아래로 제한한다."""
    if audio.size == 0 or compute_rms(audio) < 1e-8:
        return audio.astype(np.float32, copy=True)

    try:
        current_lufs = compute_lufs(audio, sample_rate)
    except (ValueError, RuntimeError):
        # 매우 짧은 오디오는 통합 LUFS를 측정할 수 없어 리미터만 적용한다.
        return limit(audio, sample_rate, ceiling_db)

    gain_db = target_lufs - current_lufs
    normalized = audio.astype(np.float64) * (10.0 ** (gain_db / 20.0))
    return limit(normalized.astype(np.float32), sample_rate, ceiling_db)
