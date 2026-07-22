"""세션 스템(드럼/베이스/일렉기타/통기타/피아노/보컬) 레벨 밸런싱.

트랙 하나를 기준(anchor)으로 삼고, 나머지 트랙을 목표 레벨에 맞춘다.
기준 트랙은 사용자가 커맨드라인에 가장 먼저 입력한 트랙으로 정하므로,
드럼이 없어도(예: 베이스+일렉기타만) 최소 2개 트랙이면 동작한다.
보컬을 포함해도 vocal_chain의 DSP는 적용하지 않고 원음 그대로 레벨만 맞춘다.
"""

import sys
from pathlib import Path

import numpy as np

from pipeline.balance import balance_levels
from pipeline.loader import load_and_normalize, match_channels, pad_to_length

# 드럼을 0dB로 두고 사용자와 협의해 정한 트랙별 목표 레벨(dB).
# 실제 anchor가 드럼이 아니어도, 두 트랙의 목표 레벨 '차이'를 offset으로 쓴다.
# vocal은 mix 모드의 "MR보다 +3dB 위" 관행을 그대로 재사용한다.
STEM_TARGET_LEVELS_DB: dict[str, float] = {
    "drum": 0.0,
    "bass": -2.0,
    "electric_guitar": -5.0,
    "acoustic_guitar": -6.0,
    "piano": -5.0,
    "vocal": 3.0,
}

# 스템 이름 -> typer가 만드는 실제 CLI 플래그 (kebab-case).
_STEM_CLI_FLAGS: dict[str, str] = {
    "--drum": "drum",
    "--bass": "bass",
    "--electric-guitar": "electric_guitar",
    "--acoustic-guitar": "acoustic_guitar",
    "--piano": "piano",
    "--vocal": "vocal",
}


def _pick_anchor(tracks: dict[str, Path]) -> str:
    """커맨드라인에 등장한 순서 그대로, 가장 먼저 입력된 스템 이름을 기준으로 정한다."""
    for arg in sys.argv:
        name = _STEM_CLI_FLAGS.get(arg.split("=", 1)[0])
        if name is not None and name in tracks:
            return name
    return next(iter(tracks))  # sys.argv에서 못 찾을 경우(예: 코드로 직접 호출)의 대비책


def balance_stems(
    tracks: dict[str, np.ndarray], anchor: str, sample_rate: int
) -> dict[str, np.ndarray]:
    """anchor 트랙을 기준으로 나머지 트랙의 레벨을 목표 오프셋에 맞춰 반환한다."""
    anchor_audio = tracks[anchor]
    anchor_level = STEM_TARGET_LEVELS_DB[anchor]
    balanced: dict[str, np.ndarray] = {anchor: anchor_audio.astype(np.float32, copy=True)}
    for name, audio in tracks.items():
        if name == anchor:
            continue
        offset_db = STEM_TARGET_LEVELS_DB[name] - anchor_level
        balanced[name] = balance_levels(audio, anchor_audio, sample_rate, offset_db=offset_db)
    return balanced


def load_and_balance_stems(tracks: dict[str, Path]) -> tuple[dict[str, np.ndarray], str, int]:
    """스템 파일들을 불러와 길이를 맞추고, 자동으로 고른 anchor 기준으로 밸런싱한다."""
    anchor = _pick_anchor(tracks)
    anchor_audio, sample_rate = load_and_normalize(tracks[anchor])

    audio_by_name: dict[str, np.ndarray] = {anchor: anchor_audio}
    for name, path in tracks.items():
        if name != anchor:
            audio_by_name[name], _ = load_and_normalize(path, sample_rate)

    # 프레임 수(첫 축)를 기준으로 길이를 맞춘 뒤, 하나라도 스테레오면 채널을
    # 스테레오로 통일한다. (믹스에서 그대로 더할 수 있게)
    length = max(audio.shape[0] for audio in audio_by_name.values())
    names = list(audio_by_name)
    padded = [pad_to_length(audio, length) for audio in audio_by_name.values()]
    aligned = dict(zip(names, match_channels(*padded)))
    return balance_stems(aligned, anchor, sample_rate), anchor, sample_rate
