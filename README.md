# Aurafine M1

Aurafine은 보컬 트랙과 MR(반주) 트랙을 입력받아 보컬을 보정하고, 레벨을 맞춘 뒤 마스터링된 WAV 파일을 만드는 Python CLI 프로젝트입니다.

M1은 웹 화면이나 머신러닝 모델 없이, 정해진 DSP 규칙을 적용하는 명령줄 도구입니다.

## 처리 흐름

```text
입력 파일
  -> 44.1kHz / 24-bit WAV 정규화
  -> 보컬 체인 (하이패스 → 디에서 → EQ → 컴프레서 → 리버브)
  -> 보컬/MR 구간별 RMS 밸런싱 (mix 모드만)
  -> 믹스 (mix 모드만)
  -> -1 dBFS 리미터 및 -14 LUFS 마스터링
  -> output/ WAV 파일 저장
```

## 준비 사항

- Python 3.11 이상
- `ffmpeg`가 시스템에 설치되어 있고 터미널에서 실행 가능해야 합니다.
- PyCharm에서는 이 프로젝트 전용 가상환경(`.venv`)을 사용하는 것을 권장합니다.

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

```bash
# 보컬과 MR을 믹스한다. 리버브: dry / pop / ballad
python main.py --vocal samples/vocal.wav --mr samples/mr.wav --reverb pop

# 보컬만 처리한다. 리버브와 MR 밸런싱은 생략하고 마스터링은 적용한다.
python main.py --vocal samples/vocal.wav --mode voice
```

`mix` 모드에서는 `--mr` 옵션이 필수입니다. `voice` 모드에서는 `--mr`를 전달하지 않습니다.

## 출력

처리 결과는 `output/` 폴더에 타임스탬프를 포함한 이름으로 저장됩니다.

- `[timestamp]_mixed.wav`: 보컬과 MR을 합친 최종 마스터 파일 (`mix` 모드)
- `[timestamp]_vocal_only.wav`: 처리된 보컬 파일 (`voice` 모드 및 비교용 출력)

`samples/` 폴더의 테스트 음원은 개인 파일이므로 Git에 올리지 않습니다.

## 현재 상태

M1 파이프라인과 CLI는 구현되어 있습니다. 실행하려면 Python 3.11 이상의 프로젝트 인터프리터, 라이브러리 설치, 그리고 `ffmpeg` 준비가 필요합니다. 자동 테스트는 아직 구성되지 않았습니다.
