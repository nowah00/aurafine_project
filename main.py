"""Aurafine CLI 엔트리 포인트."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import typer

from pipeline.balance import balance_levels
from pipeline.loader import load_and_normalize
from pipeline.master import limit, master
from pipeline.stems import load_and_balance_stems
from pipeline.vocal_chain import process_vocal

app = typer.Typer(add_completion=False, help="보컬과 MR을 자동 처리하는 CLI 도구")

# Windows 기본 콘솔(cp949)은 이모지를 출력하지 못하므로 UTF-8로 강제한다.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def _align_lengths(*tracks: np.ndarray) -> tuple[np.ndarray, ...]:
    """짧은 트랙 뒤를 무음으로 채워 모든 배열의 길이를 같게 만든다."""
    length = max(track.size for track in tracks)
    return tuple(np.pad(track, (0, length - track.size)) for track in tracks)


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    """24-bit PCM WAV로 저장한다."""
    sf.write(path, audio, sample_rate, subtype="PCM_24")


def _run_stems(tracks: dict[str, Path], output_dir: Path, timestamp: str) -> None:
    """세션 스템들의 레벨을 맞춰 믹스한다. (기준 트랙: 커맨드라인에 먼저 입력된 트랙)"""
    print("🎙 Loading audio...")
    print("🎛 Balancing stems...")
    balanced, anchor_name, sample_rate = load_and_balance_stems(tracks)
    print(f"   (기준 트랙: {anchor_name})")
    mixed_audio = sum(balanced.values())

    print("🎚 Mastering mix...")
    mastered_mix = master(mixed_audio, sample_rate)
    mix_path = output_dir / f"{timestamp}_stems_mixed.wav"
    _write_wav(mix_path, mastered_mix, sample_rate)
    print(f"✅ Saved: {mix_path}")


@app.command()
def run(
    vocal: Optional[Path] = typer.Option(
        None, exists=True, dir_okay=False, help="보컬 트랙 경로 (stems 모드에서는 원음 그대로 밸런싱만 적용)"
    ),
    mr: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="MR(반주) 트랙 경로"),
    drum: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="드럼 트랙 경로"),
    bass: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="베이스 트랙 경로"),
    electric_guitar: Optional[Path] = typer.Option(
        None, exists=True, dir_okay=False, help="일렉 기타 트랙 경로"
    ),
    acoustic_guitar: Optional[Path] = typer.Option(
        None, exists=True, dir_okay=False, help="통기타 트랙 경로"
    ),
    piano: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="피아노 트랙 경로"),
    reverb: str = typer.Option("dry", help="리버브 프리셋: dry / pop / ballad"),
    mode: str = typer.Option("mix", help="mix: 보컬+MR / voice: 보컬만 / stems: 세션 악기 밸런스"),
) -> None:
    """보컬 믹스/보컬 단독, 또는 세션 스템 밸런스 WAV 파일을 저장한다."""
    if mode not in {"mix", "voice", "stems"}:
        raise typer.BadParameter("mode는 mix, voice, stems 중 하나여야 합니다.")
    if reverb not in {"dry", "pop", "ballad"}:
        raise typer.BadParameter("reverb는 dry, pop, ballad 중 하나여야 합니다.")
    if mode in {"mix", "voice"} and vocal is None:
        raise typer.BadParameter("mix/voice 모드에서는 --vocal 경로가 필요합니다.")
    if mode == "mix" and mr is None:
        raise typer.BadParameter("mix 모드에서는 --mr 경로가 필요합니다.")

    stem_tracks = {
        name: path
        for name, path in (
            ("drum", drum),
            ("bass", bass),
            ("electric_guitar", electric_guitar),
            ("acoustic_guitar", acoustic_guitar),
            ("piano", piano),
            ("vocal", vocal),
        )
        if path is not None
    }
    if mode == "stems" and len(stem_tracks) < 2:
        raise typer.BadParameter(
            "stems 모드에서는 --drum --bass --electric-guitar --acoustic-guitar --piano --vocal 중 "
            "2개 이상을 입력해야 합니다."
        )

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if mode == "stems":
        _run_stems(stem_tracks, output_dir, timestamp)
        return

    print("🎙 Loading audio...")
    vocal_audio, sample_rate = load_and_normalize(vocal)
    mr_audio: Optional[np.ndarray] = None
    if mode == "mix" and mr is not None:
        mr_audio, _ = load_and_normalize(mr, sample_rate)

    print("⚙️ Processing vocal chain...")
    processed_vocal = process_vocal(vocal_audio, sample_rate, "dry" if mode == "voice" else reverb)

    if mode == "voice":
        print("🎚 Mastering vocal...")
        mastered_vocal = master(processed_vocal, sample_rate)
        output_path = output_dir / f"{timestamp}_vocal_only.wav"
        _write_wav(output_path, mastered_vocal, sample_rate)
        print(f"✅ Saved: {output_path}")
        return

    assert mr_audio is not None  # 위의 CLI 검증으로 mix 모드에서는 항상 존재한다.
    processed_vocal, mr_audio = _align_lengths(processed_vocal, mr_audio)
    print("🎛 Balancing vocal and MR...")
    balanced_vocal = balance_levels(processed_vocal, mr_audio, sample_rate)
    mixed_audio = balanced_vocal + mr_audio

    print("🎚 Mastering mix...")
    mastered_mix = master(mixed_audio, sample_rate)
    vocal_path = output_dir / f"{timestamp}_vocal_only.wav"
    mix_path = output_dir / f"{timestamp}_mixed.wav"
    # 밸런싱 게인으로 피크가 1.0을 넘을 수 있어 저장 전에 리미터로 보호한다.
    _write_wav(vocal_path, limit(balanced_vocal, sample_rate), sample_rate)
    _write_wav(mix_path, mastered_mix, sample_rate)
    print(f"✅ Saved: {mix_path}")
    print(f"✅ Saved: {vocal_path}")


if __name__ == "__main__":
    app()
