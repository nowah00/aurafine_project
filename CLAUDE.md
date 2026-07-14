# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project status

Aurafine M1 has its directory structure, dependency list, CLI, and core DSP pipeline implemented. Treat this file as the implementation specification when extending or adjusting the pipeline.

## Product scope

Aurafine is a Python CLI audio-processing pipeline. It accepts a vocal track and, in mix mode, an MR (music/background) track; it processes the vocal, balances it against the MR, masters the result, and exports WAV files.

M1 is CLI-only and rule-based. Do not add a web server, FastAPI, database, or ML model. A web layer belongs to M2.

The user is a Python beginner. Use simple control flow, type hints, descriptive names, and concise Korean inline comments where they help explain non-obvious Python or DSP concepts.

## Project layout

```text
main.py                 # Typer CLI entry point and orchestration only
pipeline/loader.py      # format normalization and audio loading
pipeline/vocal_chain.py # vocal DSP chain
pipeline/balance.py     # one-second RMS-based vocal/MR matching
pipeline/master.py      # limiting and LUFS normalization
utils/analyzer.py       # RMS, LUFS, and spectral analysis helpers
samples/                # user-provided audio; never commit it
output/                 # generated WAV files; never commit it
requirements.txt        # pinned Python dependencies
README.md               # user-facing setup and run instructions
```

Each pipeline module exposes one clear public, type-hinted function. Keep files under 150 lines; extract helpers rather than growing a module past that limit.

## Environment

- Python 3.11+ is required (the code uses `str | Path` union syntax; the macOS system Python 3.9 crashes at import). A working venv exists at `.venv/` (Python 3.12 from Homebrew) — use `.venv/bin/python`.
- `ffmpeg` must be on PATH (installed via Homebrew at `/opt/homebrew/bin/ffmpeg`); `loader.py` shells out to it.

## Commands

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py --vocal samples/vocal.wav --mr samples/mr.wav --reverb pop
.venv/bin/python main.py --vocal samples/vocal.wav --mode voice
```

No linter or test suite is configured yet. When one is added, document its installation and command in both this file and `README.md`.

## Fixed pipeline order

1. **Load and normalize**: use ffmpeg plus librosa to make inputs 44,100 Hz, 24-bit WAV data.
2. **Process the vocal** with pedalboard in this exact order:
   1. high-pass filter at 100 Hz;
   2. gentle de-essing in the 6–10 kHz range;
   3. resonant-peak suppression and a 3–5 kHz presence boost;
   4. compressor: 4:1 ratio, RMS-derived threshold, 10 ms attack, 100 ms release;
   5. reverb preset: `dry`, `pop`, or `ballad`.
3. **Balance** the processed vocal to the MR using one-second RMS segments, with a +3 dB vocal offset (so the vocal sits above the MR) and a ±12 dB clamp.
4. **Mix** the balanced vocal and MR.
5. **Master** the final signal: limit to -1 dBFS, then normalize to -14 LUFS.
6. **Export** timestamped WAV files under `output/`.

Gain staging must occur after vocal processing and before mastering. Mastering must receive the final mix rather than the unbalanced vocal.

## Hard-won implementation notes (do not regress)

- **`pedalboard.Limiter` is unusable as a ceiling limiter**: it applies auto makeup gain (boosts a -20 dB signal by ~5 dB) and overshoots its threshold (a -0.4 dB signal comes out at 0 dBFS). `pipeline/master.py` uses a custom brickwall limiter instead (needed-gain curve → 6 ms lookahead `minimum_filter1d` → 3 ms `uniform_filter1d` smoothing → final clip guard). Do not swap it back.
- **The de-esser is dynamic, not a static EQ cut**: `vocal_chain._deess` bandpasses 6–10 kHz (scipy `sosfiltfilt`), tracks the band envelope, and reduces only above an 80th-percentile reference (3:1, max -8 dB, 30 ms gain smoothing). Thresholds were tuned against synthetic audio only — revisit with real vocals.
- **Balance gain must be interpolated, not stepped**: hard per-segment gain steps cause zipper noise. `balance.py` interpolates segment-center gains (`np.interp`) into a per-sample gain curve; near-silent segments are skipped and filled by interpolation.
- **In mix mode, `vocal_only.wav` is limited before writing** (`limit()` call in `main.py`) — balance gain can push peaks past 1.0, and a PCM_24 write would clip.
- **typer and click must be pinned together**: typer 0.12 broke against click 8.4 (`make_metavar()` signature change). Currently typer 0.26.8 + click 8.4.2, both pinned.
- The loader converts everything to **mono** — an accepted M1 simplification (MR loses its stereo image); revisit in M2.

## Modes and CLI rules

- `mix` is the default mode and requires both `--vocal` and `--mr`.
- `voice` requires `--vocal` only. It forces `dry` reverb, skips MR loading/balancing/mixing, and still applies the same limiter and -14 LUFS master stage to the vocal.
- Accept only `dry`, `pop`, and `ballad` for `--reverb`; validate invalid options with a clear Typer error.
- Print a short Korean or English progress line at each stage, for example `🎙 Loading audio...` and `⚙️ Processing vocal chain...`.

## Libraries

- `pedalboard`: vocal effects (HPF, EQ, compressor, reverb) — **not** the limiter (see notes above)
- `scipy`: de-esser band filtering and the custom limiter (direct dependency, pinned)
- `librosa`: loading and spectral analysis
- `pyloudnorm`: LUFS measurement and normalization
- `noisereduce`: optional noise reduction only; do not make it mandatory in the chain
- `soundfile`: WAV output
- `ffmpeg-python` or `subprocess`: ffmpeg conversion
- `typer` (+ pinned `click`): CLI parsing

## Implementation conventions

- Target Python 3.11+.
- Keep dependency versions pinned in `requirements.txt`.
- Use `numpy.ndarray` for audio data and pass the sample rate explicitly.
- Handle mono/stereo shapes deliberately and document the chosen convention at module boundaries.
- Do not commit source audio or generated output.
