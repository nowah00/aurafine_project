# Aurafine M1

Aurafine은 보컬 트랙과 MR(반주) 트랙을 입력받아 보컬을 보정하고, 레벨을 맞춘 뒤 마스터링된 WAV 파일을 만드는 Python CLI 프로젝트입니다. 드럼/베이스/일렉기타/통기타/피아노/보컬 중 2개 이상을 넣어 레벨만 맞추는 `stems` 모드도 있습니다 (이 모드의 보컬은 DSP 처리 없이 원음 그대로 밸런싱됩니다).

M1은 웹 화면이나 머신러닝 모델 없이, 정해진 DSP 규칙을 적용하는 명령줄 도구입니다.

## 처리 흐름

```text
입력 파일
  -> 44.1kHz / 24-bit WAV 정규화 (채널 수 보존: 모노는 모노, 스테레오는 스테레오)
  -> 보컬 체인 (하이패스 → 디에서 → EQ → 컴프레서 → 리버브)   [mix / voice 모드]
  -> 보컬/MR 구간별 RMS 밸런싱 (mix 모드만)
  -> 스템 구간별 RMS 밸런싱, 먼저 입력한 트랙 기준             [stems 모드]
  -> 믹스 (mix / stems 모드)
  -> -1 dBFS 리미터 및 -14 LUFS 마스터링
  -> output/ WAV 파일 저장
```

## 준비 사항

- Python 3.11 이상
- `ffmpeg`가 시스템에 설치되어 있고 터미널에서 실행 가능해야 합니다.
- PyCharm에서는 이 프로젝트 전용 가상환경(`.venv`)을 사용하는 것을 권장합니다.

## 설치

```bash
# macOS: Homebrew로 Python 3.12와 ffmpeg 설치 (이미 있다면 생략)
brew install python@3.12 ffmpeg

# 가상환경 생성 후 라이브러리 설치
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 사용법

```bash
# 보컬과 MR을 믹스한다. 리버브: dry / pop / ballad
.venv/bin/python main.py --vocal samples/vocal.wav --mr samples/mr.wav --reverb pop

# 보컬만 처리한다. 리버브와 MR 밸런싱은 생략하고 마스터링은 적용한다.
.venv/bin/python main.py --vocal samples/vocal.wav --mode voice

# 세션 스템의 레벨을 맞춰 믹스한다. (보컬 없음, 2개 이상이면 됨)
.venv/bin/python main.py --mode stems \
  --drum samples/drum.wav --bass samples/bass.wav \
  --electric-guitar samples/electric.wav \
  --acoustic-guitar samples/acoustic.wav \
  --piano samples/piano.wav

# 드럼 없이 베이스+일렉기타만 넣는 것도 가능하다.
.venv/bin/python main.py --mode stems \
  --bass samples/bass.wav --electric-guitar samples/electric.wav

# 보컬도 세션 트랙 중 하나로 포함할 수 있다. (DSP 없이 원음 그대로 밸런싱)
.venv/bin/python main.py --mode stems \
  --drum samples/drum.wav --bass samples/bass.wav \
  --piano samples/piano.wav --vocal samples/vocal.wav
```

`mix` 모드에서는 `--mr` 옵션이 필수입니다. `voice` 모드에서는 `--mr`를 전달하지 않습니다. `stems` 모드에서는 `--drum --bass --electric-guitar --acoustic-guitar --piano --vocal` 중 **2개 이상**을 넣으면 되고, 여섯 개를 다 넣을 필요는 없습니다. `--mr`/`--reverb`는 무시되며, `stems` 모드의 `--vocal`은 `mix`/`voice` 모드와 달리 DSP 체인 없이 원음 그대로 다른 트랙과 레벨만 맞춰집니다.

`stems` 모드는 **커맨드라인에 가장 먼저 적은 트랙**을 기준(0dB)으로 삼고, 나머지 트랙을 정해진 목표 레벨에 맞춥니다. 목표 레벨은 드럼을 0dB로 뒀을 때 베이스 -2dB, 일렉기타 -5dB, 통기타 -6dB, 피아노 -5dB, 보컬 +3dB(`mix` 모드의 "보컬은 반주보다 +3dB 위" 관행과 동일)이며, 어느 트랙이 기준이 되든 두 트랙 사이의 상대적인 차이는 항상 같게 유지됩니다. 이 값은 장르 공통 기본값이라 실제 곡으로 들어보며 조정이 필요할 수 있습니다.

## 출력

처리 결과는 `output/` 폴더에 타임스탬프를 포함한 이름으로 저장됩니다.

- `[timestamp]_mixed.wav`: 보컬과 MR을 합친 최종 마스터 파일 (`mix` 모드)
- `[timestamp]_vocal_only.wav`: 처리된 보컬 파일 (`voice` 모드 및 비교용 출력)
- `[timestamp]_stems_mixed.wav`: 스템들을 레벨 맞춰 합친 최종 마스터 파일 (`stems` 모드)

`samples/` 폴더의 테스트 음원은 개인 파일이므로 Git에 올리지 않습니다.

## 테스트

`requirements.txt`를 설치하면 pytest도 함께 설치됩니다. 프로젝트 루트에서 실행하세요.

```bash
.venv/bin/python -m pytest                    # 전체 실행 (약 2초)
.venv/bin/python -m pytest -m "not ffmpeg"    # ffmpeg가 필요한 테스트 제외
.venv/bin/python -m pytest tests/test_master.py -v   # 특정 파일만 자세히
```

테스트는 전부 코드로 만든 합성 신호(사인파 등)를 쓰기 때문에 `samples/` 폴더에 음원이 없어도 돌아갑니다. 파일 로딩 테스트만 실제로 `ffmpeg`를 실행하며, `ffmpeg`가 없는 환경에서는 자동으로 건너뜁니다.

| 파일 | 확인하는 것 |
|------|-------------|
| `tests/test_analyzer.py` | RMS·LUFS 계산, 공명 피크 탐색 |
| `tests/test_balance.py` | 목표 오프셋 도달, ±12dB 클램프, 게인 곡선이 계단식이 아닌지, 스테레오 이미지 유지 |
| `tests/test_master.py` | 리미터가 ceiling을 넘지 않는지, 조용한 신호를 임의로 키우지 않는지, -14 LUFS 도달 |
| `tests/test_stems.py` | 목표 레벨 테이블, 앵커가 바뀌어도 상대 밸런스가 같은지, 앵커 선택 규칙 |
| `tests/test_loader.py` | 44.1kHz 리샘플링, 모노/스테레오 채널 규약, 길이·채널 정렬 헬퍼 |
| `tests/test_vocal_chain.py` | 리버브 프리셋 3종, 100Hz 하이패스, 디에서가 다이내믹하게 동작하는지 |

## 현재 상태

M1 파이프라인과 CLI가 구현되어 있고, 합성 테스트 음원으로 세 모드 모두 끝까지 실행되는 것을 확인했습니다 (믹스/스템 결과: -14 LUFS, 피크 -1dBFS 이내). MR·스템은 입력의 스테레오 이미지를 그대로 유지한 채 밸런싱·믹스·마스터링됩니다 (보컬은 항상 모노로 처리되며, 스테레오 반주에 섞일 때 가운데(L=R)로 얹힙니다). 모노 입력은 모노 그대로 출력됩니다. 디에서는 치찰음이 커질 때만 반응하는 다이내믹 방식이고, 보컬/MR 밸런싱은 1초 구간 RMS를 부드럽게 보간하며 보컬을 MR보다 +3dB 위에 얹습니다. `stems` 모드는 같은 밸런싱 로직을 재사용해, 커맨드라인에 먼저 입력한 트랙을 기준으로 나머지 트랙을 정해진 목표 레벨에 맞춥니다 (2개 이상이면 드럼 없이도, 보컬을 섞어도 동작). 실제 드럼/베이스/피아노/보컬 세션 음원으로도 확인했습니다. pytest 기반 자동 테스트 85개가 구성되어 있습니다 (위 [테스트](#테스트) 참고). 린터는 아직 없습니다.
