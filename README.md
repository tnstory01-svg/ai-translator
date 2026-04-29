# AI Translator (한 / 영 → 스페인어)

복수전공(외국어 + IT) 경험을 살린 AI 번역 도구입니다.
한국어 또는 영어 원문을 **스페인어 격식체** 또는 **비즈니스 이메일** 형식으로 번역합니다.

## 동기

스페인어권 진출을 노리는 한국 직장인이 입사 직후 즉시 업무 메일을 보낼 수 있을 정도의 결과물을 만들어주는 도구를 목표로 했습니다.
단순 기계 번역으로는 격식 수준(`tú` vs `usted`), 비즈니스 정형구, 이메일 구조까지 잡아주지 못하기 때문에, AI에게 명확한 톤·구조 가이드를 system prompt로 주입하는 방식으로 해결했습니다.

## 기능

- **번역 모드 2종**
  - **격식체** — `usted` 기반, 격식 어휘, 정중한 가정법
  - **비즈니스 이메일** — Asunto / Saludo / Cuerpo / Despedida / Firma 5섹션 완성형
- **실시간 스트리밍** — 응답을 토큰 단위로 즉시 표시
- **프롬프트 캐싱 적용** — 시스템 프롬프트가 안정적이라 두 번째 요청부터 캐시 적중 (입력 토큰 비용 약 90% 절감)
- **API 키 보호** — `.env`로 분리, `.gitignore`로 커밋 차단

## 기술 스택

- Python 3.13
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) (`claude-sonnet-4-6`)
- Streamlit
- python-dotenv

## 실행 방법

### 1. 클론 + 가상환경

```bash
git clone https://github.com/tnstory01-svg/ai-translator.git
cd ai-translator
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. API 키 설정

[Anthropic Console](https://console.anthropic.com/)에서 API 키 발급 후:

```bash
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY=sk-ant-... 입력
```

또는 앱 사이드바에 직접 입력해도 됩니다.

### 3. 실행

```bash
streamlit run app.py
```

브라우저가 자동으로 열리며 (기본: http://localhost:8501) 즉시 사용 가능합니다.

## 시스템 프롬프트의 언어학적 근거

이 프로젝트의 차별화 포인트는 단순히 "AI에게 번역 시키기"가 아니라, **외국어 전공 지식을 system prompt 설계에 명시적으로 반영했다는 점**입니다. 각 규칙은 스페인어 사회언어학·화용론(pragmatics)에 근거를 두고 있습니다.

### 1. T-V 구분 (T-V distinction): `tú` vs `usted`

스페인어에는 **두 종류의 2인칭 단수**가 있습니다.

| 형태  | 사용 맥락                                   | 동사 활용  |
| ----- | -------------------------------------------- | ---------- |
| `tú`  | 친밀 관계, 동년배, 가족, 친구                 | 2인칭 단수 |
| `usted` | 처음 만나는 사람, 상급자, 고객, 공식 자리 | **3인칭 단수** |

> **언어학적 배경**: Brown & Gilman(1960)의 고전적 논문 *"The Pronouns of Power and Solidarity"* 에서 정립된 개념. 라틴어 `tu` / `vos`에서 분화. 스페인 본토는 친밀화 경향이 강해 `tú` 사용 범위가 넓지만, **라틴아메리카 비즈니스 환경에서는 여전히 `usted`가 표준**.

**프롬프트 적용**: 모든 모드에서 `usted` 강제. `tú` 사용 시 동사 활용이 달라져 (`vives` vs `vive`) 한국어 화자가 가장 흔히 실수하는 지점이라 명시적 예시 포함.

### 2. 어휘 격식 층위 (registro / lexical register)

같은 의미에도 **공식성 등급**에 따라 다른 어휘가 존재합니다. 라틴어계 어휘일수록 격식이 높습니다.

| 일상어      | 격식어                          | 어원                                     |
| ----------- | ------------------------------- | ---------------------------------------- |
| `comprar`   | `adquirir`                       | Lat. *acquirere* (취득하다)              |
| `pedir`     | `solicitar`                     | Lat. *sollicitare* (간청하다)             |
| `decir`     | `manifestar` / `comunicar`       | Lat. *manifestare* (드러내다)             |
| `empezar`   | `iniciar` / `comenzar`           | Lat. *initiare* (시작하다)                |
| `terminar`  | `concluir` / `finalizar`         | Lat. *concludere* (결론짓다)              |

> **언어학적 배경**: 스페인어는 Vulgar Latin → Old Spanish의 자연 진화 어휘(일상어)와, 르네상스 이후 Classical Latin에서 직접 차용한 학술어(*cultismos*)의 **이중 어휘 체계(doublets)** 를 가집니다. 비즈니스·학술·행정 텍스트는 후자를 선호.

**프롬프트 적용**: 자주 쓰이는 일상어/격식어 쌍을 표 형태로 직접 명시 → 모델이 단순 기계 번역으로 흐르지 않고 의식적으로 격식어를 선택하도록 유도.

### 3. 가정법(subjuntivo)과 정중성(cortesía)

스페인어에서 **명령은 직접적으로 들리며 무례하게 받아들여집니다.** 정중함을 표현하려면 가정법 + 조건법이 필수.

```
직접 명령 (무례):  Envíeme el documento.        (서류를 보내십시오.)
정중한 요청:       Le agradecería que me        (서류를 보내주신다면 감사하겠습니다.)
                   enviase el documento.
```

핵심 구조:
- `agradecería` (조건법, conditional) + `que` + `enviase` (불완전 가정법, imperfect subjunctive)
- `quisiera` (불완전 가정법) — `quiero`("원한다")보다 부드러움

> **언어학적 배경**: Brown & Levinson(1987)의 정중성 이론(Politeness Theory)에서 말하는 *negative politeness strategy* — 상대의 자율성을 침해하지 않으려는 거리두기 전략. 스페인어는 이를 **가정법 형태소(morphology)** 로 문법화한 언어.

**프롬프트 적용**: 비즈니스 이메일 모드에서 정형구로 `Le agradecería que...`, `Quisiera...`, `Le ruego que...` 등을 명시 — 한국어/영어 화자가 직역하면 빠지기 쉬운 부분.

### 4. 비인칭·수동 구문 (impersonal / passive)

부정적 사실(오류, 지연 등)을 전달할 때 **행위자를 드러내지 않는 구문**으로 직설성을 완화합니다.

```
직설:    Hicimos un error.            (우리가 실수를 했습니다.)
완화:    Se ha producido un error.   (오류가 발생하였습니다.)
```

- `se` 비인칭 구문 (impersonal `se`)
- 책임 소재를 흐리고 사건 자체에 초점

> **언어학적 배경**: 스페인어 `se` 구문은 *medio-passive*로 분류되며, 한국어의 "발생되었습니다", 일본어의 「ました」 수동형과 유사한 **face-saving** 기능. 비즈니스/관료 문서의 핵심 자질.

**프롬프트 적용**: 비즈니스 이메일 모드에 사과·문제 보고 정형구 (`Lamento los inconvenientes...`, `Se ha producido...`) 명시.

### 5. 이메일 구조의 정형성 (formulaic structure)

스페인어 비즈니스 이메일은 **5단 구조가 거의 의무적**입니다.

```
Asunto      (제목 — 명사구, 25자 이내)
Saludo      (인사 — Estimado/a Sr./Sra. + 성)
Cuerpo      (본문 — 단락별 단일 요점)
Despedida   (맺음말 — Atentamente / Cordialmente / Un cordial saludo)
Firma       (서명)
```

각 위치별 정형구(formulaic phrases)가 거의 고정되어 있어, **개인의 창의성보다 관습 준수가 더 중요**.

> **언어학적 배경**: 장르 분석(genre analysis, Swales 1990) 관점에서 비즈니스 이메일은 *highly conventionalized genre* — 정형구 사용은 비원어민의 능숙도(proficiency)를 가늠하는 핵심 지표.

**프롬프트 적용**: 단순 문장이 들어와도 모델이 5단 구조로 **확장**하도록 명시. 사용자가 결과물을 그대로 복사·붙여넣기만 하면 송신 가능한 상태로 만드는 것이 목표.

### 6. 형식 규약 (formatting conventions)

언어학적 규칙은 아니지만 **현지 적응(localization)** 의 핵심 요소.

| 항목      | 영미식                       | 스페인식                       |
| --------- | ---------------------------- | ------------------------------ |
| 날짜      | `03/15/2026` (월/일/년)       | `15 de marzo de 2026` (일/월/년) |
| 천 단위   | `1,000.50`                    | `1.000,50`                     |
| 통화 위치 | `$1,000`                      | `1.000 €` (금액 뒤)            |

**프롬프트 적용**: 한국어/영어 원문에 숫자나 날짜가 들어오면 자동으로 스페인 표기로 변환. 영미식 그대로 두면 현지에서 즉시 비원어민으로 식별됨.

---

이상의 6개 영역은 **번역 결과의 자연스러움보다 적절성(appropriateness)** 을 결정하는 요소들입니다. 단순히 의미를 옮기는 것이 아니라, "이 글이 스페인어 원어민이 보기에 사회적으로 적절한가"를 통과시키는 것이 이 프로젝트의 목표였고, 시스템 프롬프트는 그 목표를 모델이 따라올 수 있도록 명시적으로 가이드하는 방식으로 작성되었습니다.

## 학습 포인트 (포트폴리오 어필용)

- AI 페어 코딩 도구로 만든 코드를 한 줄씩 이해하며 검토
- API 키 관리, `.gitignore` 등 기본 보안 의식
- Anthropic API의 prompt caching, streaming 기능 활용
- 외국어 전공 경험을 시스템 프롬프트 설계에 직접 반영 (`usted` vs `tú`, 비즈니스 정형구, 스페인식 날짜/숫자 표기 등)

## 개선 아이디어

- [ ] 번역 히스토리 저장 (SQLite)
- [ ] 번역 결과 대비 표시 (원문 vs 번역문 side-by-side)
- [ ] 어조 슬라이더 (격식 ↔ 친근)
- [ ] 다른 언어쌍 추가 (포르투갈어, 프랑스어 등)
- [ ] Docker 컨테이너화

## 라이선스

학습 목적의 토이 프로젝트입니다.
