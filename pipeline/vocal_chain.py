"""pedalboard 기반 보컬 프로세싱 체인."""

from typing import Literal

import numpy as np
from pedalboard import Compressor, HighpassFilter, PeakFilter, Pedalboard, Reverb

from utils.analyzer import compute_rms, find_resonant_peaks

ReverbPreset = Literal["dry", "pop", "ballad"]

_REVERB_SETTINGS = {
    "pop": {"room_size": 0.35, "damping": 0.55, "wet_level": 0.18, "dry_level": 0.9},
    "ballad": {"room_size": 0.7, "damping": 0.4, "wet_level": 0.32, "dry_level": 0.85},
}


def process_vocal(
    audio: np.ndarray, sample_rate: int, reverb: ReverbPreset = "dry"
) -> np.ndarray:
    """하이패스→디에서→EQ→컴프레서→리버브 순서로 보컬을 처리한다."""
    if reverb not in {"dry", "pop", "ballad"}:
        raise ValueError("reverb는 dry, pop, ballad 중 하나여야 합니다.")
    if audio.size == 0:
        return audio.astype(np.float32, copy=True)

    rms = compute_rms(audio)
    rms_db = 20.0 * np.log10(max(rms, 1e-8))
    threshold_db = float(np.clip(rms_db - 6.0, -45.0, -8.0))

    effects = [
        HighpassFilter(cutoff_frequency_hz=100.0),
        # 8kHz 주변을 살짝 줄여 치찰음(s, sh)을 완화하는 간단한 디에서 역할이다.
        PeakFilter(cutoff_frequency_hz=8000.0, gain_db=-2.5, q=1.2),
    ]
    effects.extend(
        PeakFilter(cutoff_frequency_hz=frequency, gain_db=-3.0, q=5.0)
        for frequency in find_resonant_peaks(audio, sample_rate)
    )
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

    processed = Pedalboard(effects)(audio.astype(np.float32), sample_rate)
    return np.asarray(processed, dtype=np.float32)
