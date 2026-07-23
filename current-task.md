# Current Task — Aurafine 개발 로그 / 진행상황

> 이 문서는 Aurafine 프로젝트의 개발 로그와 진행상황을 추적합니다.
> 상세 스펙은 `CLAUDE.md`, 사용자용 안내는 `README.md`를 참고하세요.
> 앞으로 작업을 진행할 때마다 아래 **진행상황 로그**에 계속 업데이트합니다.

_최종 업데이트: 2026-07-23_

---

## 프로젝트 개요

Aurafine은 보컬/MR 트랙을 입력받아 보컬 보정 → 레벨 밸런싱 → 마스터링을 거쳐 WAV로 내보내는 Python CLI 오디오 처리 파이프라인입니다. 별도의 `stems` 모드로 세션 트랙(드럼/베이스/일렉기타/통기타/피아노/보컬 중 2개 이상)의 레벨만 맞추는 기능도 있습니다.

- **마일스톤**: M1 (CLI-only, 규칙 기반). 웹 서버·DB·ML 모델은 M2 범위.
- **환경**: Python 3.11+ (실제 `.venv`는 Homebrew Python 3.12), `ffmpeg` PATH 필요.
- **실행 예시**: `.venv/bin/python main.py --vocal samples/vocal.wav --mr samples/mr.wav --reverb pop`

---

## 모드 요약

| 모드 | 필수 입력 | 동작 |
|------|-----------|------|
| `mix` (기본) | `--vocal`, `--mr` | 보컬 체인 → 보컬/MR 밸런싱(+3dB) → 믹스 → 마스터링 |
| `voice` | `--vocal` | 보컬 체인(리버브 강제 `dry`) → 마스터링. MR 관련 단계 생략 |
| `stems` | 6개 트랙 중 2개 이상 | 원음 밸런싱 → 믹스 → 마스터링. 보컬 체인 미적용, `--mr`/`--reverb` 무시 |

---

## 구현 현황 (M1)

- [x] 디렉터리 구조 · 의존성 목록 · CLI · 코어 DSP 파이프라인
- [x] `pipeline/loader.py` — ffmpeg+librosa로 44.1kHz/24-bit 정규화, 채널 수 보존(모노 1D / 스테레오 2D), 채널 정렬 헬퍼(`to_stereo`/`match_channels`/`pad_to_length`)
- [x] `pipeline/vocal_chain.py` — HPF(100Hz) → 다이내믹 디에서(6–10kHz) → EQ(공진 억제+3–5kHz 프레즌스) → 컴프레서(4:1) → 리버브 프리셋
- [x] `pipeline/balance.py` — 1초 RMS 구간 기반 레벨 매칭(보간, ±12dB 클램프). mix/stems 공용
- [x] `pipeline/stems.py` — 스템 목표 레벨 테이블, 앵커 선택, 밸런싱
- [x] `pipeline/master.py` — 커스텀 브릭월 리미터(-1dBFS) → -14 LUFS 정규화
- [x] `utils/analyzer.py` — RMS/LUFS/스펙트럼 분석 헬퍼
- [x] 세 모드 모두 합성 음원 + 실제 세션 음원으로 엔드투엔드 동작 확인
- [x] 자동 테스트 스위트 — pytest 85개 (`tests/`), 합성 신호만 사용, 약 2초
- [ ] 린터 (미구성)

---

## 미해결 / 향후 과제

- **린터 도입**: 아직 없음 (ruff 검토). 추가 시 `CLAUDE.md`/`AGENTS.md`와 `README.md`에 설치·실행법 문서화 필요.
- **테스트 미커버 영역**: `main.py`의 CLI 플래그 검증·모드 라우팅·WAV 내보내기는 아직 테스트가 없음 (엔드투엔드 성격이라 별도 설계 필요).
- **디에서 임계값 재조정**: 합성 음원 기준으로 튜닝됨 → 실제 보컬로 검증 필요.
- **스템 목표 레벨 테이블**: 장르 공통 기본값. 실제 스템으로 귀로 확인, 필요 시 장르별 프리셋 검토.
- **스테레오 지원 (완료, 2026-07-22)**: MR·스템은 스테레오 이미지 보존. 보컬은 모노 처리 유지(디에서/공명 억제가 모노 전용) → 보컬 자체의 스테레오 처리는 M2 과제로 남김.
- **M2 범위**: 웹 레이어(FastAPI 등), DB, ML 모델, 스테레오 보컬 처리.

---

## 진행상황 로그

### 2026-07-23
- 환경 점검: `.venv` Python 3.12.13, ffmpeg `/opt/homebrew/bin/ffmpeg`, 의존성 전부 import OK, CLI `--help` 정상. 작업트리 클린 / origin/main 동기화 상태.
- **pytest 테스트 스위트 도입 (85개, 약 2.3초 전체 통과)**.
  - `pytest.ini` 신설: `pythonpath = .`(테스트에서 `pipeline`/`utils` import 가능), `testpaths = tests`, `ffmpeg` 마커 등록.
  - `tests/conftest.py`: 공용 픽스처(`sample_rate`)와 신호 헬퍼(`sine`/`stereo`/`peak_db`/`band_energy`). **모든 테스트가 합성 신호만 사용** → `samples/` 음원 없이도 실행됨.
  - `test_analyzer.py`(13) RMS·LUFS·공명 피크 / `test_balance.py`(13) 오프셋·클램프·게인 곡선 연속성·스테레오 이미지 / `test_master.py`(17) 리미터·LUFS / `test_stems.py`(15) 목표 테이블·앵커 / `test_loader.py`(14) 채널 규약·리샘플링 / `test_vocal_chain.py`(13) 프리셋·HPF·디에서.
  - **회귀 방지 테스트 명시**: pedalboard.Limiter의 자동 메이크업 게인 부재(조용한 신호 그대로), ceiling 오버슛 없음(-0.4dB → -1dBFS 이하), 스테레오 채널 링크 게인(L/R 비율 유지), 앵커가 바뀌어도 스템 간 상대 밸런스 동일 — CLAUDE.md "do not regress" 항목과 1:1 대응.
  - 로더 테스트만 실제 ffmpeg를 호출 → `@pytest.mark.ffmpeg` + ffmpeg 부재 시 자동 skip. `-m "not ffmpeg"`로 제외 가능.
  - `vocal_chain._deess` / `stems._pick_anchor`는 동작 자체가 회귀 방지 대상이라 private이지만 직접 테스트 (스펙에 예외로 명시).
  - **초기 실패 4건은 전부 테스트 픽스처 문제였고 코드 버그 아님**: 픽스처의 트랙 간 레벨 차이가 `balance_levels`의 ±12dB 클램프를 넘어 목표 오프셋에 미달(예: 13.98dB 필요 → 12dB 클램프 → 정확히 1.98dB 부족). 픽스처 레벨을 좁히고, 이 함정을 CLAUDE.md/AGENTS.md의 "테스트 작성 규칙"에 기록.
  - `pytest==9.1.1`을 `requirements.txt`에 개발용으로 고정, `.gitignore`에 `.pytest_cache/` 추가.
  - `CLAUDE.md`/`AGENTS.md`(동기화)에 테스트 실행법·작성 규칙 섹션 추가, `README.md`에 사용자용 "테스트" 섹션(파일별 커버리지 표) 추가.
- **참고**: `main.py`가 145줄로 스펙의 150줄 상한에 근접. 다음에 `main.py`를 확장할 때는 헬퍼 추출이 먼저 필요할 수 있음.

### 2026-07-22
- `git fetch`로 origin/main과 동기화 확인 (최신 상태).
- `.gitignore`에 `.DS_Store` 추가 → 커밋(`04611d8`) → origin/main push 완료.
- `current-task.md` 개발 로그 문서 초안 작성 (기존 `CLAUDE.md`/`README.md`/git 히스토리 기반).
- **스테레오 믹싱 지원 추가**: 모노 강제 로직을 걷어내고 입력 채널 자동 감지·보존으로 전환.
  - 채널 규약 확정: 모노 1D `(N,)` / 스테레오 2D `(N, 2)` (soundfile 저장 규약과 동일).
  - `loader`: `mono` 파라미터 추가(보컬만 `True`), `to_stereo`/`match_channels`/`pad_to_length` 헬퍼 신설.
  - `balance`: 프레임 축(`shape[0]`) 기준으로 수정, 게인 곡선을 두 채널에 공통 적용(`[:, None]`).
  - `master.limit`: L/R **공통 게인**(채널 max 기준)으로 리미팅 → 스테레오 이미지 보존.
  - `main`/`stems`: 길이 정렬·채널 정렬 후 믹스. 모노 보컬은 스테레오 MR에 가운데(L=R)로 업믹스, `vocal_only.wav`는 모노 유지.
  - 실제 스테레오 샘플로 검증: mix/stems 출력 ch=2·-14 LUFS·-1dBFS, L≠R(이미지 보존 확인). 모노 입력→모노 출력도 확인.
  - `CLAUDE.md`/`README.md`/`current-task.md` 문서 갱신.
- **문서 재설계**: `CLAUDE.md`의 "Project layout"을 파일별 역할·공개 API 정확히 명시하도록 다시 설계(부정확했던 "모듈당 공개 함수 1개" 규칙 수정, 의존성 방향 명시). `AGENTS.md`(Codex 스펙)도 헤더만 제외하고 동일 내용으로 동기화.
- **실제 샘플 스테레오 믹싱 확인**: gaudiolab 4트랙(drum 기준 + bass/piano/vocal, 전부 스테레오)으로 stems 모드 실행 → 출력 스테레오(ch=2), -14.00 LUFS, -1.00 dBFS, L-R 상관 0.81(이미지 보존). 사용자 청취 확인 완료.

### 이전 커밋 이력 (참고)
- `b9e3d0b` 보컬을 stems 모드의 원음 트랙으로 허용
- `710eba2` stems 모드를 5개 전부가 아닌 2개 이상으로 실행 가능하게 변경
- `0995d92` 드럼 기준 다중 악기 밸런싱 stems 모드 추가
- `c632011` 마스터링 수정, 다이내믹 디에서 및 부드러운 보컬 밸런싱 추가
- `f29f9d8` 개발 중간 커밋
- `ad932ad` 초기 Aurafine M1 파이프라인
