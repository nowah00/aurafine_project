# Current Task — Aurafine 개발 로그 / 진행상황

> 이 문서는 Aurafine 프로젝트의 개발 로그와 진행상황을 추적합니다.
> 상세 스펙은 `CLAUDE.md`, 사용자용 안내는 `README.md`를 참고하세요.
> 앞으로 작업을 진행할 때마다 아래 **진행상황 로그**에 계속 업데이트합니다.

_최종 업데이트: 2026-07-22_

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
- [x] `pipeline/loader.py` — ffmpeg+librosa로 44.1kHz/24-bit/모노 정규화
- [x] `pipeline/vocal_chain.py` — HPF(100Hz) → 다이내믹 디에서(6–10kHz) → EQ(공진 억제+3–5kHz 프레즌스) → 컴프레서(4:1) → 리버브 프리셋
- [x] `pipeline/balance.py` — 1초 RMS 구간 기반 레벨 매칭(보간, ±12dB 클램프). mix/stems 공용
- [x] `pipeline/stems.py` — 스템 목표 레벨 테이블, 앵커 선택, 밸런싱
- [x] `pipeline/master.py` — 커스텀 브릭월 리미터(-1dBFS) → -14 LUFS 정규화
- [x] `utils/analyzer.py` — RMS/LUFS/스펙트럼 분석 헬퍼
- [x] 세 모드 모두 합성 음원 + 실제 세션 음원으로 엔드투엔드 동작 확인
- [ ] 자동 테스트 스위트 (미구성)
- [ ] 린터 (미구성)

---

## 미해결 / 향후 과제

- **자동 테스트·린터 도입**: 아직 없음. 추가 시 `CLAUDE.md`와 `README.md`에 설치·실행법 문서화 필요.
- **디에서 임계값 재조정**: 합성 음원 기준으로 튜닝됨 → 실제 보컬로 검증 필요.
- **스템 목표 레벨 테이블**: 장르 공통 기본값. 실제 스템으로 귀로 확인, 필요 시 장르별 프리셋 검토.
- **모노 변환**: MR 스테레오 이미지 손실 — M1 단순화. M2에서 재검토.
- **M2 범위**: 웹 레이어(FastAPI 등), DB, ML 모델.

---

## 진행상황 로그

### 2026-07-22
- `git fetch`로 origin/main과 동기화 확인 (최신 상태).
- `.gitignore`에 `.DS_Store` 추가 → 커밋(`04611d8`) → origin/main push 완료.
- `current-task.md` 개발 로그 문서 초안 작성 (기존 `CLAUDE.md`/`README.md`/git 히스토리 기반).

### 이전 커밋 이력 (참고)
- `b9e3d0b` 보컬을 stems 모드의 원음 트랙으로 허용
- `710eba2` stems 모드를 5개 전부가 아닌 2개 이상으로 실행 가능하게 변경
- `0995d92` 드럼 기준 다중 악기 밸런싱 stems 모드 추가
- `c632011` 마스터링 수정, 다이내믹 디에서 및 부드러운 보컬 밸런싱 추가
- `f29f9d8` 개발 중간 커밋
- `ad932ad` 초기 Aurafine M1 파이프라인
