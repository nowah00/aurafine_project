기본 파일# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project status

This repo currently contains only PyCharm's default scaffold (`main.py`). The target project — **Aurafine M1 MVP** — has not been built yet. The structure and behavior below is the plan to implement, not yet-existing code to browse; use it as the spec when scaffolding files.

## What Aurafine is

A CLI audio processing pipeline (Python) that takes a vocal track and an MR (Music/Background) track, runs the vocal through a DSP processing chain, balances levels between vocal and MR, masters the result, and exports a mixed WAV file. M1 is CLI-only and rule-based (no web server, no ML models) — a FastAPI web layer is planned for M2 but is out of scope for now.

The user is a Python beginner. When implementing or explaining pipeline code, briefly explain non-obvious Python concepts as they come up, and prefer Korean inline comments where they aid a beginner (per the conventions below).

## Target project structure

```
aurafine/
├── main.py              # CLI entry point (typer)
├── pipeline/
│   ├── __init__.py
│   ├── loader.py        # Audio loading & format normalization (ffmpeg/librosa)
│   ├── vocal_chain.py   # Vocal processing chain (pedalboard)
│   ├── balance.py       # Vocal/MR level matching
│   └── master.py        # Limiter + LUFS normalization
├── utils/
│   ├── __init__.py
│   └── analyzer.py      # Audio analysis helpers (RMS, LUFS, spectral)
├── samples/             # Test audio files (user-provided, not committed)
├── output/              # Processed files land here
├── requirements.txt
└── README.md
```

Each pipeline module should expose one clear, type-hinted function. Keep every file under 150 lines — split rather than let a module grow past that.

## Commands

Once scaffolded:
- Install deps: `pip install -r requirements.txt`
- Run full mix: `python main.py --vocal samples/vocal.wav --mr samples/mr.wav --reverb pop`
- Voice-only mode (no MR, no reverb mix): `python main.py --vocal samples/vocal.wav --mode voice`

There is no build step, linter, or test suite configured yet — set these up (and document the commands here) when they're added.

## Processing pipeline (fixed order)

1. **Load & normalize** (`loader.py`) — convert input to 44100Hz / 24-bit WAV via `ffmpeg` (subprocess) + `librosa`.
2. **Vocal chain** (`vocal_chain.py`, via `pedalboard`), applied in this order:
   - High-pass filter, cutoff 100Hz
   - De-esser targeting 6-10kHz, gentle reduction
   - EQ: auto-detect and suppress resonant peaks, boost presence (3-5kHz)
   - Compressor: 4:1 ratio, threshold auto-derived from RMS, 10ms attack / 100ms release
   - Reverb: one of 3 presets selected via CLI arg — `dry` / `pop` / `ballad`
3. **Gain staging** (`balance.py`) — match vocal RMS to MR RMS, analyzed in 1s segments (not a single global gain).
4. **Mix** — sum processed vocal + MR.
5. **Master** (`master.py`) — limiter at -1dBFS ceiling, then loudness-normalize to -14 LUFS via `pyloudnorm`.
6. **Export** — write `output/[timestamp]_mixed.wav` and `output/[timestamp]_vocal_only.wav` (kept separate for A/B comparison).

This order matters: gain staging happens after the vocal chain (so compression/EQ changes are accounted for) and before mastering (which should see the final mix level, not the pre-balance one).

## Libraries

- `pedalboard` (Spotify) — vocal chain DSP
- `librosa` — audio analysis
- `pyloudnorm` — LUFS measurement & normalization
- `noisereduce` — optional noise reduction
- `soundfile` — WAV read/write
- `ffmpeg-python` — format conversion
- `typer` — CLI argument parsing (chosen over `argparse` for being more beginner-friendly)

## Conventions

- Python 3.11+.
- Pin versions in `requirements.txt`.
- Type-hint every pipeline function.
- Emit progress to the console at each pipeline stage, e.g. `"🎙 Loading audio..."`, `"⚙️ Processing vocal chain..."`.
- Favor Korean inline comments where they help explain a concept to a Python beginner.
- README.md should cover: project description, install (`pip install -r requirements.txt`), and usage examples.
