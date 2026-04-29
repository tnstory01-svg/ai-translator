"""
AI Translator — 한국어/영어 → 스페인어 (격식체 / 비즈니스 메일)

Anthropic Claude Sonnet 4.6 + Streamlit
- 프롬프트 캐싱으로 시스템 프롬프트 비용 약 90% 절감
- 스트리밍으로 응답 즉시 표시
- API 키는 .env 또는 사이드바 입력으로 주입 (소스에 절대 하드코딩하지 않음)
"""

import os
import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = "claude-sonnet-4-6"


SYSTEM_PROMPT_FORMAL = """당신은 한국어/영어를 **스페인어 격식체(formal register)** 로 번역하는 전문 번역가입니다.

## 핵심 원칙

1. **존칭 대명사 `usted` 사용** — `tú`(친근체)는 사용하지 않습니다. 동사 활용도 3인칭 단수에 맞춥니다.
   - 예: "당신은 어디 사세요?" → "¿Dónde vive usted?" (O) / "¿Dónde vives?" (X)

2. **격식 어휘 선호** — 일상어 대신 공식적이거나 라틴어 기반 어휘를 선택합니다.
   - "comprar" → "adquirir" (구매하다 → 취득하다)
   - "ayudar" → "asistir / colaborar"
   - "decir" → "indicar / comunicar / manifestar"
   - "pedir" → "solicitar"
   - "necesitar" → "requerir / precisar"
   - "empezar" → "iniciar / comenzar"
   - "terminar" → "concluir / finalizar"

3. **완곡어법(eufemismo)과 가정법(subjuntivo)** — 직설적 명령문 대신 정중한 요청 형태로.
   - "Envíeme el documento" 보다 "Le agradecería que me enviase el documento"
   - "Quiero..." 보다 "Quisiera... / Me gustaría..."

4. **호칭** — 이름을 모를 때는 `señor / señora` 사용. 직책이 있으면 `Don / Doña + 이름` 또는 `Estimado/a Sr./Sra. + 성`.

5. **줄임말 금지** — `pa'`(para), `na'`(nada) 같은 구어 축약형은 절대 사용하지 않습니다.

## 출력 형식

번역 결과만 출력합니다. 주석, 설명, 영어 부연설명 일체 금지.
다만 원문에 모호한 부분(예: 화자의 성별이 번역에 영향을 미치지만 원문에 명시되지 않은 경우)이 있으면, 번역 아래에 `[참고]` 한 줄로만 짧게 명시합니다.
"""


SYSTEM_PROMPT_BUSINESS = """당신은 한국어/영어를 **스페인어 비즈니스 이메일** 형식으로 번역/작성하는 전문 번역가입니다.
사용자는 입사 직후 즉시 업무에 투입할 수 있는 수준의 결과물을 기대합니다.

## 이메일 구조 (반드시 준수)

```
[Asunto]
(제목 — 간결하고 핵심을 담은 명사구. 25자 이내 권장)

[Saludo]
(인사말 — 수신자를 알면 "Estimado/a Sr./Sra. [성]:", 모르면 "Estimados señores:")

[Cuerpo]
(본문 — 단락별로 한 가지 요점만. 첫 문단에 목적, 중간 문단에 세부, 마지막 문단에 다음 단계 또는 요청)

[Despedida]
(맺음말 — 격식 순서: "Atentamente," > "Cordialmente," > "Un cordial saludo,")

[Firma]
(서명 — 사용자가 별도로 지시하지 않았다면 `[Su nombre]` 자리표시자로 둠)
```

## 표현 규칙

1. **`usted` + 격식 어휘** (격식체와 동일). `tú` 절대 금지.

2. **비즈니스 정형구(formulaic phrases)를 적극 활용**:
   - 도입: "Me dirijo a usted con el fin de..." / "Por la presente,..." / "En relación con..."
   - 문의: "Le agradecería que me proporcionase información sobre..."
   - 요청: "Le ruego que..." / "Quedo a la espera de su respuesta"
   - 첨부: "Adjunto a la presente encontrará..."
   - 사과: "Lamento los inconvenientes que esto pueda ocasionar"
   - 감사: "Le agradezco de antemano su atención" / "Quedo a su entera disposición"

3. **수동태와 비인격(impersonal) 구문**으로 직설성 완화:
   - "Hicimos un error" → "Se ha producido un error" (오류가 발생하였습니다)

4. **숫자/날짜 형식**:
   - 날짜: "15 de marzo de 2026" (스페인식). 숫자 표기는 "15/03/2026" (월/일 순서 절대 X).
   - 금액: "1.000,50 €" (천 단위는 마침표, 소수점은 쉼표).

5. **이모지/느낌표/구어체 금지**. `¡Gracias!` 대신 `Le agradezco`.

## 출력 형식

위의 `[Asunto] / [Saludo] / [Cuerpo] / [Despedida] / [Firma]` 5개 섹션을 모두 포함한 완성된 이메일을 출력합니다.
원문이 단순 문장이어도 비즈니스 이메일 형식으로 확장하여 작성합니다 (사용자가 그대로 복사해서 보낼 수 있도록).

번역 결과 외 설명은 출력하지 않습니다. 단, 원문에 모호한 정보(수신자, 발신자 정보 등)가 있으면 이메일 아래에 `[확인 필요]` 섹션으로 짧게 정리합니다.
"""


@st.cache_resource
def get_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def translate_stream(client: anthropic.Anthropic, system_prompt: str, user_text: str):
    """Sonnet 4.6에 스트리밍 요청. 시스템 프롬프트는 캐싱."""
    with client.messages.stream(
        model=MODEL_ID,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    ) as stream:
        for text in stream.text_stream:
            yield text
        # 스트림 종료 후 usage 정보를 세션 상태에 저장
        final = stream.get_final_message()
        st.session_state["last_usage"] = final.usage


def main():
    st.set_page_config(page_title="AI Translator (ES)", page_icon=None, layout="centered")
    st.title("AI 스페인어 번역기")
    st.caption("한국어/영어 → 스페인어 격식체 또는 비즈니스 이메일")

    with st.sidebar:
        st.subheader("설정")

        env_key = os.getenv("ANTHROPIC_API_KEY", "")
        api_key = st.text_input(
            "Anthropic API Key",
            value=env_key,
            type="password",
            help=".env 파일에 ANTHROPIC_API_KEY를 넣어두면 자동으로 채워집니다.",
        )

        mode = st.radio(
            "번역 모드",
            options=["격식체 (formal)", "비즈니스 이메일"],
            index=0,
        )

        st.divider()
        st.markdown("**모델**: `claude-sonnet-4-6`")
        st.markdown("**프롬프트 캐싱**: 활성")

        if "last_usage" in st.session_state:
            u = st.session_state["last_usage"]
            st.markdown("---")
            st.markdown("**최근 요청 토큰**")
            st.text(
                f"입력: {u.input_tokens}\n"
                f"캐시 작성: {u.cache_creation_input_tokens}\n"
                f"캐시 읽기: {u.cache_read_input_tokens}\n"
                f"출력: {u.output_tokens}"
            )

    user_text = st.text_area(
        "원문 (한국어 또는 영어)",
        height=180,
        placeholder="예: 견적서를 받지 못했는데 일정이 어떻게 되나요?",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        translate = st.button("번역", type="primary", use_container_width=True)
    with col2:
        if st.button("초기화", use_container_width=False):
            st.session_state.pop("last_usage", None)
            st.rerun()

    if translate:
        if not api_key:
            st.error("API 키를 입력하거나 .env 파일에 ANTHROPIC_API_KEY를 설정하세요.")
            return
        if not user_text.strip():
            st.warning("번역할 원문을 입력해주세요.")
            return

        system_prompt = (
            SYSTEM_PROMPT_FORMAL if mode.startswith("격식체") else SYSTEM_PROMPT_BUSINESS
        )

        client = get_client(api_key)

        st.subheader("번역 결과")
        try:
            st.write_stream(translate_stream(client, system_prompt, user_text))
        except anthropic.AuthenticationError:
            st.error("API 키가 유효하지 않습니다. 콘솔에서 키를 다시 확인해주세요.")
        except anthropic.RateLimitError:
            st.error("요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")
        except anthropic.APIError as e:
            st.error(f"API 오류 ({e.status_code}): {e.message}")


if __name__ == "__main__":
    main()
