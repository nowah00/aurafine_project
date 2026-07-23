# AGENTS.md

This file provides guidance to Codex when working in this repository.

## Project status

Aurafine M1 has its directory structure, dependency list, CLI, and core DSP pipeline implemented. Treat this file as the implementation specification when extending or adjusting the pipeline.

## Product scope

Aurafine is a Python CLI audio-processing pipeline. It accepts a vocal track and, in mix mode, an MR (music/background) track; it processes the vocal, balances it against the MR, masters the result, and exports WAV files. A separate `stems` mode balances any 2+ of a six-track session (drum, bass, electric guitar, acoustic guitar, piano, vocal) against each other instead of a vocal/MR pair — vocal is accepted raw here, with no DSP chain applied.

M1 is CLI-only and rule-based. Do not add a web server, FastAPI, database, or ML model. A web layer belongs to M2.

The user is a Python beginner. Use simple control flow, type hints, descriptive names, and concise Korean inline comments where they help explain non-obvious Python or DSP concepts.

## Project layout

```text
main.py                 # Typer CLI: flag validation, orchestration, WAV export
pipeline/loader.py      # audio load + format/channel normalization + channel-layout helpers
pipeline/vocal_chain.py # vocal DSP chain (mono only): HPF → de-ess → EQ → compressor → reverb
pipeline/balance.py     # generic RMS level matching (track vs. reference, mono/stereo)
pipeline/stems.py       # stems-mode target table, anchor pick, load + per-track balancing
pipeline/master.py      # channel-linked brickwall limiter + LUFS normalization
utils/analyzer.py       # stateless RMS / LUFS / spectral-peak helpers
samples/                # user-provided audio; never commit it
output/                 # generated WAV files; never commit it
tests/                  # pytest suite (synthetic signals only; no audio files needed)
pytest.ini              # pytest config (pythonpath, testpaths, markers)
requirements.txt        # pinned Python dependencies (incl. pytest)
README.md               # user-facing setup and run instructions
current-task.md         # dev log / progress tracker (append per work session)
CLAUDE.md / AGENTS.md   # implementation spec for Claude Code / Codex — keep the two in sync
```

### Per-file responsibilities and public API

Each module owns one responsibility and exposes only the type-hinted functions listed below (names prefixed `_` are private helpers; don't call them across modules). Keep every file under 150 lines — extract helpers rather than grow past the limit. The dependency direction is one-way: `main` → `pipeline/*` → `utils/analyzer`; `pipeline/loader` is the shared audio-format layer that `main` and `stems` both import.

- **`main.py`** — CLI entry point and the *only* orchestration layer. Public: `run(...)` (the Typer command). Validates mode/flags, loads via `loader`, routes each mode (`mix` / `voice` / `stems`) through the right pipeline stages, prints progress lines, and writes timestamped WAVs. Private helpers: `_align_lengths` (frame-axis padding via `loader.pad_to_length`), `_write_wav` (PCM_24), `_run_stems` (stems orchestration). No DSP math lives here.
- **`pipeline/loader.py`** — all audio I/O and channel-layout normalization. Public:
  - `load_and_normalize(path, sample_rate=44100, mono=False) -> (audio, sr)` — ffmpeg to 44.1 kHz/24-bit, then librosa. Preserves input channels unless `mono=True`; returns mono `(N,)` or stereo `(N, 2)` (3+ channels truncated to the first 2).
  - `pad_to_length(audio, length)` — zero-pad the frame axis, mono/stereo aware.
  - `to_stereo(audio)` — upmix mono to dual-mono `(N, 2)`.
  - `match_channels(*tracks)` — if any track is stereo, upmix the rest so they can be summed.
- **`pipeline/vocal_chain.py`** — the vocal effect chain, **mono in / mono out**; never runs in `stems` mode. Public: `process_vocal(audio, sample_rate, reverb='dry') -> audio`. Private: `_deess` (dynamic de-esser), `_smooth`; module constants `ReverbPreset`, `_REVERB_SETTINGS`.
- **`pipeline/balance.py`** — one generic level matcher shared by every mode. Public: `balance_levels(track, reference, sample_rate, segment_seconds=1.0, offset_db=3.0) -> track_scaled`. Builds a smooth per-sample gain curve; applies the same curve to both stereo channels.
- **`pipeline/stems.py`** — stems-mode balancing built on `balance_levels`. Public: `STEM_TARGET_LEVELS_DB` (target table), `balance_stems(tracks, anchor, sample_rate)`, `load_and_balance_stems(tracks) -> (balanced_dict, anchor_name, sr)`. Private: `_pick_anchor` (scans `sys.argv`), `_STEM_CLI_FLAGS`. Loads raw (no vocal chain), aligns length + channels, balances each track against the anchor.
- **`pipeline/master.py`** — final loudness/peak stage. Public: `limit(audio, sample_rate, ceiling_db=-1.0)` (channel-linked brickwall limiter) and `master(audio, sample_rate, target_lufs=-14.0, ceiling_db=-1.0)` (LUFS-normalize then limit).
- **`utils/analyzer.py`** — stateless numeric helpers with no audio I/O. Public: `compute_rms(audio)`, `compute_lufs(audio, sample_rate)`, `find_resonant_peaks(audio, sample_rate, max_peaks=3)`. `compute_rms`/`compute_lufs` accept mono or stereo; `find_resonant_peaks` is mono/vocal-only.

## Environment

- Python 3.11+ is required (the code uses `str | Path` union syntax; the macOS system Python 3.9 crashes at import). A working venv exists at `.venv/` (Python 3.12 from Homebrew) — use `.venv/bin/python`.
- `ffmpeg` must be on PATH (installed via Homebrew at `/opt/homebrew/bin/ffmpeg`); `loader.py` shells out to it.

## Commands

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py --vocal samples/vocal.wav --mr samples/mr.wav --reverb pop
.venv/bin/python main.py --vocal samples/vocal.wav --mode voice
```

### Tests

```bash
.venv/bin/python -m pytest          # full suite (~2s)
.venv/bin/python -m pytest -m "not ffmpeg"   # skip the tests that shell out to ffmpeg
```

`pytest.ini` sets `pythonpath = .` so tests can `import pipeline...` / `import utils...`; `testpaths = tests`. `tests/conftest.py` holds the shared fixtures and signal helpers (`sine`, `stereo`, `peak_db`, `band_energy`) — every test builds its own synthetic audio, so the suite never touches `samples/` and runs without any user audio.

Test-writing rules:

- **Watch the ±12 dB clamp when picking fixture levels.** `balance_levels` caps its gain at ±12 dB, so a fixture whose tracks differ by more than that will silently miss the target offset and the assertion failure will look like a bug in the code. Keep test tracks within a few dB of each other unless the clamp itself is what you're testing.
- **pyloudnorm needs ≥ 0.4 s of audio** for an integrated-loudness reading; LUFS assertions use 5-second signals. Shorter audio exercises the `master` fallback path (limiter only).
- `tests/test_master.py` and the stems anchor tests are **regression guards** for the "do not regress" notes below (no makeup gain, no ceiling overshoot, channel-linked stereo gain, anchor-independent balance). Don't weaken them.
- Private helpers are tested directly where the behavior itself is the regression target (`vocal_chain._deess`, `stems._pick_anchor`); this is the one sanctioned exception to the "don't call `_`-prefixed functions across modules" rule.

No linter is configured yet. When one is added, document its installation and command in both this file and `README.md`.

## Fixed pipeline order

1. **Load and normalize**: use ffmpeg plus librosa to make inputs 44,100 Hz, 24-bit WAV data. Channel count is preserved by default (mono stays 1-D `(N,)`, stereo becomes 2-D `(N, 2)`); the vocal is the one exception — it is always loaded mono (`load_and_normalize(..., mono=True)`) because the de-esser and resonant-peak finder are mono-only.
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

## Stems mode pipeline order

`stems` mode skips the vocal chain entirely — it takes 2 to 6 raw tracks (any subset of drum, bass, electric guitar, acoustic guitar, piano, vocal) and just balances, mixes, and masters them:

1. **Pick the anchor track**: whichever of `--drum`/`--bass`/`--electric-guitar`/`--acoustic-guitar`/`--piano`/`--vocal` appears first on the command line (scanned from `sys.argv` in `pipeline/stems._pick_anchor`) becomes the reference track. It is never gain-adjusted. If a track's flag can't be found in `sys.argv` (e.g. the function is called from other code, not the CLI), the first dict entry is used as a fallback.
2. **Load and normalize** every provided track the same way as step 1 of the mix/voice pipeline. Vocal is loaded raw here — `process_vocal` (HPF/de-ess/EQ/compressor/reverb) is never called in `stems` mode.
3. **Balance** each non-anchor track against the anchor using `balance_levels` (same one-second RMS/interpolation machinery as vocal/MR balancing). The target offset between any two tracks is the difference of their entries in `pipeline/stems.STEM_TARGET_LEVELS_DB` (drum 0 dB, bass -2 dB, electric guitar -5 dB, acoustic guitar -6 dB, piano -5 dB, vocal +3 dB — the vocal figure reuses the same "+3 dB over the backing" convention as `mix` mode), so the same relative balance holds no matter which track ends up as anchor. ±12 dB clamp applies as usual.
4. **Mix** all balanced tracks by summing them.
5. **Master** the summed mix exactly like `mix` mode: limit to -1 dBFS, then normalize to -14 LUFS.
6. **Export** a single `[timestamp]_stems_mixed.wav` under `output/`.

These target levels are genre-agnostic defaults agreed with the user, not a physical constant — revisit by ear against real stems, and consider per-genre presets (like the `reverb` presets) if a single fixed table proves too generic.

## Hard-won implementation notes (do not regress)

- **`pedalboard.Limiter` is unusable as a ceiling limiter**: it applies auto makeup gain (boosts a -20 dB signal by ~5 dB) and overshoots its threshold (a -0.4 dB signal comes out at 0 dBFS). `pipeline/master.py` uses a custom brickwall limiter instead (needed-gain curve → 6 ms lookahead `minimum_filter1d` → 3 ms `uniform_filter1d` smoothing → final clip guard). Do not swap it back.
- **The de-esser is dynamic, not a static EQ cut**: `vocal_chain._deess` bandpasses 6–10 kHz (scipy `sosfiltfilt`), tracks the band envelope, and reduces only above an 80th-percentile reference (3:1, max -8 dB, 30 ms gain smoothing). Thresholds were tuned against synthetic audio only — revisit with real vocals.
- **Balance gain must be interpolated, not stepped**: hard per-segment gain steps cause zipper noise. `balance.py` interpolates segment-center gains (`np.interp`) into a per-sample gain curve; near-silent segments are skipped and filled by interpolation.
- **`balance_levels` is generic, not vocal-specific**: its parameters are `track`/`reference`/`offset_db`, not `vocal`/`mr`/`vocal_offset_db` — both `mix` mode (vocal vs. MR, +3 dB) and `stems` mode (each instrument vs. anchor, per-instrument offset) call the same function. Don't re-fork this logic per mode.
- **Stems mode has no fixed anchor**: since any 2+ of the 5 instruments can be provided, `pipeline/stems.STEM_TARGET_LEVELS_DB` stores each instrument's level relative to a virtual drum-at-0dB scale, and the actual per-run offset is always `TARGET[track] - TARGET[anchor]`. This is what makes the balance identical regardless of which track happens to be the anchor — don't special-case "drum is anchor" logic back in.
- **In mix mode, `vocal_only.wav` is limited before writing** (`limit()` call in `main.py`) — balance gain can push peaks past 1.0, and a PCM_24 write would clip. It stays mono (the vocal is never upmixed for this file).
- **Stereo is channel-linked, never per-channel**: the audio convention is mono 1-D `(N,)` / stereo 2-D `(N, 2)` (samples-first, matching soundfile). `balance.py` applies one shared gain curve to both channels (`gain_curve[:, None]`) and `master.limit` derives its gain from the per-sample **max across channels** — computing gain independently per channel would shift the stereo image. When mixing a mono track with a stereo one, upmix the mono to dual-mono first via `loader.match_channels` / `loader.to_stereo`; length alignment uses `loader.pad_to_length` (frame axis only). Do not reintroduce `array.size`-based length/padding math — it counts channels×frames and breaks on stereo.
- **typer and click must be pinned together**: typer 0.12 broke against click 8.4 (`make_metavar()` signature change). Currently typer 0.26.8 + click 8.4.2, both pinned.
- The loader **preserves input channels** (mono→1-D, stereo→2-D `(N, 2)`, 3+ channels truncated to the first 2). MR and stems keep their stereo image through balance/mix/master; only the vocal is force-downmixed to mono. Full stereo *vocal processing* is still deferred to M2.

## Modes and CLI rules

- `mix` is the default mode and requires both `--vocal` and `--mr`.
- `voice` requires `--vocal` only. It forces `dry` reverb, skips MR loading/balancing/mixing, and still applies the same limiter and -14 LUFS master stage to the vocal.
- `stems` requires at least 2 of `--drum`, `--bass`, `--electric-guitar`, `--acoustic-guitar`, `--piano`, and `--vocal` (any subset, not all six); it ignores `--mr` and `--reverb` entirely, and `--vocal` here is a plain raw track like any other stem (no vocal chain runs in this mode). The anchor track is whichever of those flags was typed first on the command line.
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
