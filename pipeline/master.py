"""마스터링: -1dBFS 리미팅과 -14 LUFS 정규화."""

import numpy as np
from pedalboard import Limiter

from utils.analyzer import compute_lufs, compute_rms


def _limit(audio: np.ndarray, sample_rate: int, ceiling_db: float) -> np.ndarray:
    """pedalboard 리미터를 적용하는 내부 헬퍼."""
    limited = Limiter(threshold_db=ceiling_db, release_ms=100.0)(audio, sample_rate)
    return np.asarray(limited, dtype=np.float32)


def master(
    audio: np.ndarray,
    sample_rate: int,
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
) -> np.ndarray:
    """리미터 후 목표 LUFS로 맞추고, 마지막 피크도 안전하게 제한한다."""
    if audio.size == 0 or compute_rms(audio) < 1e-8:
        return audio.astype(np.float32, copy=True)

    limited = _limit(audio.astype(np.float32), sample_rate, ceiling_db)
    try:
        current_lufs = compute_lufs(limited, sample_rate)
    except (ValueError, RuntimeError):
        # 매우 짧은 오디오는 통합 LUFS를 측정할 수 없어 리미터 결과만 사용한다.
        return limited

    gain_db = target_lufs - current_lufs
    normalized = limited * (10.0 ** (gain_db / 20.0))
    # LUFS 보정으로 피크가 다시 올라갈 수 있으므로 출력 직전에 한 번 더 보호한다.
    return _limit(normalized.astype(np.float32), sample_rate, ceiling_db)
