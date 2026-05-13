from __future__ import annotations

"""
Deployable HTML frontend + FastAPI backend for AI Translator.

API keys are read only from server-side environment variables. The browser
never receives provider API keys.
"""

import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import anthropic
import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi import Request as FastAPIRequest
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import MODEL_ID, SYSTEM_PROMPT_BUSINESS, SYSTEM_PROMPT_FORMAL

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB_PATH = BASE_DIR / "data" / "history.sqlite3"
ENV_PATH = BASE_DIR / ".env"

DEFAULT_ANTHROPIC_MODEL = MODEL_ID
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
PLACEHOLDER_PREFIXES = (
    "sk-ant-여기에",
    "sk-여기에",
    "AIza여기에",
    "여기에",
)

app = FastAPI(title="AI Translator", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000)
    mode: Literal["formal", "business"] = "formal"


class ProviderSettingsRequest(BaseModel):
    provider: Literal["auto", "anthropic", "openai", "gemini", "openai-compatible"] = "auto"
    api_key: str = Field(..., min_length=1, max_length=4096)
    model: str | None = Field(default=None, max_length=256)
    base_url: str | None = Field(default=None, max_length=2048)


class TranslateResponse(BaseModel):
    translation: str
    provider: str
    model: str
    usage: dict[str, int | None]
    history_id: int | None = None


class HistoryItem(BaseModel):
    id: int
    created_at: str
    provider: str
    model: str
    mode: Literal["formal", "business"]
    source_text: str
    translation: str
    input_tokens: int | None
    cache_creation_input_tokens: int | None
    cache_read_input_tokens: int | None
    output_tokens: int | None


class HistoryResponse(BaseModel):
    history_enabled: bool
    items: list[HistoryItem]


class ProviderSettingsResponse(BaseModel):
    saved: bool
    provider: str
    model: str | None
    base_url: str | None


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    label: str
    api_key: str | None
    model: str | None
    base_url: str | None = None
    config_error: str | None = None

    @property
    def configured(self) -> bool:
        return self.api_key is not None and self.model is not None and self.config_error is None


@dataclass(frozen=True)
class TranslationResult:
    text: str
    provider: str
    model: str
    usage: dict[str, int | None]


def clean_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def env_write_is_allowed(request: FastAPIRequest) -> bool:
    if os.getenv("ALLOW_ENV_WRITE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    client_host = request.client.host if request.client else ""
    return client_host in {"127.0.0.1", "::1", "localhost"}


def quote_env_value(value: str) -> str:
    if not value:
        return ""
    if any(char.isspace() for char in value) or any(char in value for char in ['"', "#", "="]):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def update_env_file(updates: dict[str, str]) -> None:
    ENV_PATH.touch(exist_ok=True)
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in remaining:
            next_lines.append(f"{key}={quote_env_value(remaining.pop(key))}")
        else:
            next_lines.append(line)

    if remaining and next_lines and next_lines[-1].strip():
        next_lines.append("")
    for key, value in remaining.items():
        next_lines.append(f"{key}={quote_env_value(value)}")

    ENV_PATH.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    for key, value in updates.items():
        os.environ[key] = value


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    return any(value.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def first_real_env(*names: str) -> str | None:
    for name in names:
        value = clean_env(name)
        if value and not is_placeholder(value):
            return value
    return None


def detect_provider() -> str:
    explicit = clean_env("AI_PROVIDER")
    if explicit and explicit.lower() not in {"auto", "detect"}:
        return explicit.lower()

    if clean_env("AI_BASE_URL") or clean_env("OPENAI_COMPATIBLE_BASE_URL"):
        return "openai-compatible"

    api_key = first_real_env("AI_API_KEY")
    if api_key:
        if api_key.startswith("sk-ant-"):
            return "anthropic"
        if api_key.startswith("AIza"):
            return "gemini"
        return "openai"

    if first_real_env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if first_real_env("OPENAI_API_KEY"):
        return "openai"
    if first_real_env("GEMINI_API_KEY"):
        return "gemini"
    if first_real_env("OPENAI_COMPATIBLE_API_KEY"):
        return "openai-compatible"
    return "anthropic"


def get_provider_config() -> ProviderConfig:
    provider = detect_provider()
    model_override = clean_env("AI_MODEL")
    base_override = clean_env("AI_BASE_URL")

    if provider == "anthropic":
        return ProviderConfig(
            provider="anthropic",
            label="Anthropic",
            api_key=first_real_env("AI_API_KEY", "ANTHROPIC_API_KEY"),
            model=model_override or clean_env("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
        )

    if provider == "openai":
        return ProviderConfig(
            provider="openai",
            label="OpenAI",
            api_key=first_real_env("AI_API_KEY", "OPENAI_API_KEY"),
            model=model_override or clean_env("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
            base_url=base_override or clean_env("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL,
        )

    if provider == "gemini":
        return ProviderConfig(
            provider="gemini",
            label="Google Gemini",
            api_key=first_real_env("AI_API_KEY", "GEMINI_API_KEY"),
            model=model_override or clean_env("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
            base_url=base_override
            or clean_env("GEMINI_BASE_URL")
            or DEFAULT_GEMINI_OPENAI_BASE_URL,
        )

    if provider in {"openai-compatible", "compatible", "custom"}:
        api_key = first_real_env("AI_API_KEY", "OPENAI_COMPATIBLE_API_KEY")
        model = model_override or clean_env("OPENAI_COMPATIBLE_MODEL")
        base_url = base_override or clean_env("OPENAI_COMPATIBLE_BASE_URL")
        missing = []
        if not model:
            missing.append("AI_MODEL")
        if not base_url:
            missing.append("AI_BASE_URL")
        return ProviderConfig(
            provider="openai-compatible",
            label="OpenAI-compatible",
            api_key=api_key,
            model=model,
            base_url=base_url,
            config_error=f"Missing {', '.join(missing)}." if missing else None,
        )

    return ProviderConfig(
        provider=provider,
        label=provider,
        api_key=None,
        model=None,
        config_error=f"Unsupported AI_PROVIDER: {provider}",
    )


def get_app_password() -> str | None:
    password = os.getenv("APP_PASSWORD", "").strip()
    return password or None


def password_is_valid(candidate: str | None) -> bool:
    expected = get_app_password()
    if expected is None:
        return True
    return bool(candidate) and secrets.compare_digest(candidate, expected)


def require_access(
    x_app_password: str | None = Header(default=None, alias="X-App-Password"),
) -> None:
    if not password_is_valid(x_app_password):
        raise HTTPException(status_code=401, detail="Invalid app password.")


def history_is_enabled() -> bool:
    value = os.getenv("SAVE_HISTORY", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def get_db_path() -> Path:
    raw_path = os.getenv("TRANSLATION_DB_PATH", "").strip()
    if not raw_path:
        return DEFAULT_DB_PATH
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def connect_history_db() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_history_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(translations)").fetchall()
    }
    if "provider" not in columns:
        connection.execute(
            "ALTER TABLE translations ADD COLUMN provider TEXT NOT NULL DEFAULT 'anthropic'"
        )
    if "model" not in columns:
        connection.execute(
            "ALTER TABLE translations ADD COLUMN model TEXT NOT NULL DEFAULT ''"
        )


def init_history_db() -> None:
    if not history_is_enabled():
        return
    with connect_history_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'anthropic',
                model TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL,
                source_text TEXT NOT NULL,
                translation TEXT NOT NULL,
                input_tokens INTEGER,
                cache_creation_input_tokens INTEGER,
                cache_read_input_tokens INTEGER,
                output_tokens INTEGER
            )
            """
        )
        ensure_history_columns(connection)


def save_history_entry(
    request: TranslateRequest,
    result: TranslationResult,
) -> int | None:
    if not history_is_enabled():
        return None
    init_history_db()
    with connect_history_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO translations (
                created_at,
                provider,
                model,
                mode,
                source_text,
                translation,
                input_tokens,
                cache_creation_input_tokens,
                cache_read_input_tokens,
                output_tokens
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                result.provider,
                result.model,
                request.mode,
                request.text.strip(),
                result.text,
                result.usage.get("input_tokens"),
                result.usage.get("cache_creation_input_tokens"),
                result.usage.get("cache_read_input_tokens"),
                result.usage.get("output_tokens"),
            ),
        )
        return int(cursor.lastrowid)


def system_prompt_for(mode: str) -> str:
    return SYSTEM_PROMPT_FORMAL if mode == "formal" else SYSTEM_PROMPT_BUSINESS


def extract_anthropic_text(message: anthropic.types.Message) -> str:
    parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def openai_chat_endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def extract_openai_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        ).strip()
    return ""


def parse_openai_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)
    if error:
        return str(error)
    return str(data.get("detail") or response.reason_phrase)


def translate_anthropic(config: ProviderConfig, request: TranslateRequest) -> TranslationResult:
    if config.api_key is None or config.model is None:
        raise HTTPException(status_code=503, detail="Anthropic API key is not configured.")

    client = anthropic.Anthropic(api_key=config.api_key)
    try:
        message = client.messages.create(
            model=config.model,
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "2048")),
            system=[
                {
                    "type": "text",
                    "text": system_prompt_for(request.mode),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": request.text.strip()}],
        )
    except anthropic.AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key.") from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(status_code=429, detail="Anthropic rate limit exceeded.") from exc
    except anthropic.APIError as exc:
        status_code = exc.status_code if exc.status_code is not None else 502
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    usage = message.usage
    return TranslationResult(
        text=extract_anthropic_text(message),
        provider=config.provider,
        model=config.model,
        usage={
            "input_tokens": usage.input_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens,
            "output_tokens": usage.output_tokens,
        },
    )


def translate_openai_compatible(
    config: ProviderConfig,
    request: TranslateRequest,
) -> TranslationResult:
    if config.api_key is None:
        raise HTTPException(status_code=503, detail=f"{config.label} API key is not configured.")
    if config.model is None:
        raise HTTPException(status_code=503, detail=f"{config.label} model is not configured.")
    if config.base_url is None:
        raise HTTPException(status_code=503, detail=f"{config.label} base URL is not configured.")

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt_for(request.mode)},
            {"role": "user", "content": request.text.strip()},
        ],
        "max_tokens": int(os.getenv("AI_MAX_TOKENS", "2048")),
    }

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                openai_chat_endpoint(config.base_url),
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=parse_openai_error(response),
            )
        data = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"{config.label} request timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    usage = data.get("usage") or {}
    return TranslationResult(
        text=extract_openai_text(data),
        provider=config.provider,
        model=str(data.get("model") or config.model),
        usage={
            "input_tokens": usage.get("prompt_tokens"),
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
            "output_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    )


def translate_with_active_provider(request: TranslateRequest) -> TranslationResult:
    config = get_provider_config()
    if config.config_error:
        raise HTTPException(status_code=503, detail=config.config_error)
    if not config.configured:
        raise HTTPException(
            status_code=503,
            detail=f"{config.label} API key is not configured.",
        )
    if config.provider == "anthropic":
        return translate_anthropic(config, request)
    return translate_openai_compatible(config, request)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.head("/")
def index_head() -> Response:
    return Response()


@app.get("/api/health")
def health(
    x_app_password: str | None = Header(default=None, alias="X-App-Password"),
) -> dict[str, str | bool | None]:
    auth_required = get_app_password() is not None
    authenticated = password_is_valid(x_app_password)
    config = get_provider_config()
    return {
        "auth_required": auth_required,
        "authenticated": authenticated,
        "configured": config.configured if authenticated else False,
        "config_error": config.config_error,
        "history_enabled": history_is_enabled(),
        "provider": config.provider,
        "provider_label": config.label,
        "model": config.model,
    }


@app.get("/api/history", response_model=HistoryResponse)
def list_history(
    _: None = Depends(require_access),
    limit: int = Query(default=30, ge=1, le=100),
) -> HistoryResponse:
    if not history_is_enabled():
        return HistoryResponse(history_enabled=False, items=[])
    init_history_db()
    with connect_history_db() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                provider,
                model,
                mode,
                source_text,
                translation,
                input_tokens,
                cache_creation_input_tokens,
                cache_read_input_tokens,
                output_tokens
            FROM translations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return HistoryResponse(
        history_enabled=True,
        items=[HistoryItem(**dict(row)) for row in rows],
    )


@app.delete("/api/history")
def clear_history(_: None = Depends(require_access)) -> dict[str, int | bool]:
    if not history_is_enabled():
        return {"history_enabled": False, "deleted": 0}
    init_history_db()
    with connect_history_db() as connection:
        cursor = connection.execute("DELETE FROM translations")
        return {"history_enabled": True, "deleted": cursor.rowcount}


@app.post("/api/settings/provider", response_model=ProviderSettingsResponse)
def save_provider_settings(
    settings: ProviderSettingsRequest,
    request: FastAPIRequest,
    _: None = Depends(require_access),
) -> ProviderSettingsResponse:
    if not env_write_is_allowed(request):
        raise HTTPException(
            status_code=403,
            detail="Writing .env from the browser is allowed only from localhost.",
        )

    updates = {
        "AI_PROVIDER": settings.provider,
        "AI_API_KEY": settings.api_key.strip(),
        "AI_MODEL": (settings.model or "").strip(),
        "AI_BASE_URL": (settings.base_url or "").strip(),
    }

    update_env_file(updates)
    config = get_provider_config()
    return ProviderSettingsResponse(
        saved=True,
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
    )


@app.post("/api/translate", response_model=TranslateResponse)
def translate(
    request: TranslateRequest,
    _: None = Depends(require_access),
) -> TranslateResponse:
    result = translate_with_active_provider(request)
    history_id = save_history_entry(request, result)
    return TranslateResponse(
        translation=result.text,
        provider=result.provider,
        model=result.model,
        usage=result.usage,
        history_id=history_id,
    )
