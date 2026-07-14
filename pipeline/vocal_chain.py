"""pedalboard 기반 보컬 프로세싱 체인.

처리 순서: 하이패스 → 디에서 → EQ → 컴프레서 → 리버브
"""

from typing import Literal

import numpy as np
from pedalboard import Compressor, HighpassFilter, PeakFilter, Pedalboard, Reverb
from scipy.signal import butter, sosfiltfilt

from utils.analyzer import compute_rms, find_resonant_peaks

ReverbPreset = Literal["dry", "pop", "ballad"]

_REVERB_SETTINGS = {
    "pop": {"room_size": 0.35, "damping": 0.55, "wet_level": 0.18, "dry_level": 0.9},
    "ballad": {"room_size": 0.7, "damping": 0.4, "wet_level": 0.32, "dry_level": 0.85},
}


def _smooth(values: np.ndarray, sample_rate: int, milliseconds: float) -> np.ndarray:
    """이동 평균으로 신호를 부드럽게 만든다. (급격한 게인 변화 방지)"""
    window = max(1, int(sample_rate * milliseconds / 1000.0))
    kernel = np.ones(window, dtype=np.float64) / window
    return np.convolve(values, kernel, mode="same")


def _deess(
    audio: np.ndarray, sample_rate: int, max_reduction_db: float = 8.0
) -> np.ndarray:
    """치찰음(6~10kHz)이 순간적으로 커질 때만 그 대역을 줄이는 다이내믹 디에서.

    고정 EQ와 달리, 치찰음 대역의 에너지를 실시간으로 추적해서
    평소보다 두드러지는 순간에만 게인을 줄인다.
    """
    # 1) 6~10kHz 대역만 뽑아낸다. (sosfiltfilt: 위상 왜곡 없는 양방향 필터)
    sos = butter(4, [6000.0, 10000.0], btype="bandpass", fs=sample_rate, output="sos")
    sibilance_band = sosfiltfilt(sos, audio.astype(np.float64))

    # 2) 대역 에너지의 시간 흐름(엔벨로프)을 10ms 단위로 추적한다.
    envelope = np.sqrt(_smooth(np.square(sibilance_band), sample_rate, 10.0))
    reference = float(np.percentile(envelope, 80))  # "평상시" 치찰음 레벨 기준
    if reference < 1e-8:
        return audio.astype(np.float32, copy=True)

    # 3) 기준을 넘는 만큼만 부드럽게(3:1) 줄인다. 최대 감쇠는 max_reduction_db.
    over_db = 20.0 * np.log10(np.maximum(envelope / reference, 1.0))
    reduction_db = np.clip(over_db * (1.0 - 1.0 / 3.0), 0.0, max_reduction_db)
    gain = 10.0 ** (-_smooth(reduction_db, sample_rate, 30.0) / 20.0)

    # 4) 원음에서 치찰음 대역만 줄인 뒤 다시 합친다.
    deessed = audio.astype(np.float64) - sibilance_band + sibilance_band * gain
    return deessed.astype(np.float32)


def process_vocal(
    audio: np.ndarray, sample_rate: int, reverb: ReverbPreset = "dry"
) -> np.ndarray:
    """하이패스 → 디에서 → EQ → 컴프레서 → 리버브 순서로 보컬을 처리한다."""
    if reverb not in {"dry", "pop", "ballad"}:
        raise ValueError("reverb는 dry, pop, ballad 중 하나여야 합니다.")
    if audio.size == 0:
        return audio.astype(np.float32, copy=True)

    # 1~2단계: 하이패스로 저음 잡음을 거른 뒤 다이내믹 디에서를 적용한다.
    highpassed = Pedalboard([HighpassFilter(cutoff_frequency_hz=100.0)])(
        audio.astype(np.float32), sample_rate
    )
    deessed = _deess(np.asarray(highpassed, dtype=np.float32), sample_rate)

    rms = compute_rms(deessed)
    rms_db = 20.0 * np.log10(max(rms, 1e-8))
    threshold_db = float(np.clip(rms_db - 6.0, -45.0, -8.0))

    # 3~5단계: 공명 억제 EQ → 존재감 부스트 → 컴프레서 → 리버브
    effects = [
        PeakFilter(cutoff_frequency_hz=frequency, gain_db=-3.0, q=5.0)
        for frequency in find_resonant_peaks(deessed, sample_rate)
    ]
    effects.extend(
        [
            PeakFilter(cutoff_frequency_hz=4000.0, gain_db=2.5, q=0.9),
            Compressor(
                threshold_db=threshold_db,
                ratio=4.0,
                attack_ms=10.0,
                release_ms=100.0,
            ),
        ]
    )
    if reverb != "dry":
        effects.append(Reverb(**_REVERB_SETTINGS[reverb]))

    processed = Pedalboard(effects)(deessed, sample_rate)
    return np.asarray(processed, dtype=np.float32)
