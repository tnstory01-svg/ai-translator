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
