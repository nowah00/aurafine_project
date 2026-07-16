"""세션 스템(드럼/베이스/일렉기타/통기타/피아노) 레벨 밸런싱.

드럼을 0dB 기준으로 삼고, 나머지 스템을 정해진 목표 오프셋에 맞춘다.
오프셋 값은 장르에 상관없이 쓸 수 있도록 사용자와 협의해 정한 기본값이며,
실제 곡으로 들어보며 조정이 필요할 수 있다.
"""

import numpy as np

from pipeline.balance import balance_levels

# 드럼 대비 목표 레벨(dB). 값이 작을수록(음수가 클수록) 드럼보다 뒤로 물러난다.
STEM_OFFSETS_DB: dict[str, float] = {
    "bass": -2.0,
    "electric_guitar": -5.0,
    "acoustic_guitar": -6.0,
    "piano": -5.0,
}


def balance_stems(
    drum: np.ndarray,
    bass: np.ndarray,
    electric_guitar: np.ndarray,
    acoustic_guitar: np.ndarray,
    piano: np.ndarray,
    sample_rate: int,
) -> dict[str, np.ndarray]:
    """드럼을 기준으로 나머지 스템의 레벨을 목표 오프셋에 맞춰 반환한다."""
    stems = {
        "bass": bass,
        "electric_guitar": electric_guitar,
        "acoustic_guitar": acoustic_guitar,
        "piano": piano,
    }
    balanced: dict[str, np.ndarray] = {"drum": drum.astype(np.float32, copy=True)}
    for name, audio in stems.items():
        balanced[name] = balance_levels(
            audio, drum, sample_rate, offset_db=STEM_OFFSETS_DB[name]
        )
    return balanced
