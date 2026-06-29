from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="aigc-service", alias="AIGC_APP_NAME")
    port: int = Field(default=8094, alias="AIGC_PORT")
    profile: str = Field(default="local", alias="AIGC_PROFILE")
    response_wrap: bool = Field(default=True, alias="AIGC_RESPONSE_WRAP")

    database_url: str = Field(
        default="mysql+pymysql://<username>:<password>@<host>:3306/tj_aigc?charset=utf8mb4",
        alias="AIGC_DATABASE_URL",
    )

    redis_url: str | None = Field(default=None, alias="AIGC_REDIS_URL")
    redis_host: str = Field(default="127.0.0.1", alias="AIGC_REDIS_HOST")
    redis_port: int = Field(default=6379, alias="AIGC_REDIS_PORT")
    redis_db: int = Field(default=0, alias="AIGC_REDIS_DB")
    redis_password: str | None = Field(default=None, alias="AIGC_REDIS_PASSWORD")

    chat_provider: str = Field(default="qwen", alias="AIGC_CHAT_PROVIDER")
    chat_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="AIGC_CHAT_BASE_URL",
    )
    chat_api_key: str = Field(default="", alias="AIGC_CHAT_API_KEY")
    chat_model: str = Field(default="qwen-plus", alias="AIGC_CHAT_MODEL")

    embedding_provider: str = Field(default="qwen", alias="AIGC_EMBEDDING_PROVIDER")
    embedding_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="AIGC_EMBEDDING_BASE_URL",
    )
    embedding_api_key: str = Field(default="", alias="AIGC_EMBEDDING_API_KEY")
    embedding_model: str = Field(default="text-embedding-v3", alias="AIGC_EMBEDDING_MODEL")

    rag_vector_weight: float = Field(default=0.7, alias="AIGC_RAG_VECTOR_WEIGHT")
    rag_keyword_weight: float = Field(default=0.3, alias="AIGC_RAG_KEYWORD_WEIGHT")
    rag_keyword_candidate_multiplier: int = Field(default=3, alias="AIGC_RAG_KEYWORD_CANDIDATE_MULTIPLIER")
    rag_keyword_min_term_length: int = Field(default=2, alias="AIGC_RAG_KEYWORD_MIN_TERM_LENGTH")

    nacos_server_addr: str = Field(default="<host>:8848", alias="AIGC_NACOS_SERVER_ADDR")
    nacos_username: str = Field(default="", alias="AIGC_NACOS_USERNAME")
    nacos_password: str = Field(default="", alias="AIGC_NACOS_PASSWORD")
    nacos_namespace: str = Field(default="", alias="AIGC_NACOS_NAMESPACE")
    nacos_group: str = Field(default="DEFAULT_GROUP", alias="AIGC_NACOS_GROUP")
    nacos_timeout_ms: int = Field(default=20000, alias="AIGC_NACOS_TIMEOUT_MS")
    nacos_text_prompt_data_id: str = Field(default="text-system-chat-message.txt", alias="AIGC_NACOS_TEXT_PROMPT_DATA_ID")

    # 微服务调用地址（直连模式，跳过网关）
    course_service_url: str = Field(default="http://localhost:8086", alias="AIGC_COURSE_SERVICE_URL")
    search_service_url: str = Field(default="http://localhost:8083", alias="AIGC_SEARCH_SERVICE_URL")
    trade_service_url: str = Field(default="http://localhost:8088", alias="AIGC_TRADE_SERVICE_URL")

    session_title: str = Field(default="Hello，我是天机AI助理", alias="AIGC_SESSION_TITLE")
    session_describe: str = Field(
        default="我是由天机学堂倾力打造的智能助理，我不仅能推荐课程、答疑解惑，还能为您激发创意、畅聊心事。",
        alias="AIGC_SESSION_DESCRIBE",
    )
    session_examples_json: str = Field(default="[]", alias="AIGC_SESSION_EXAMPLES_JSON")

    def session_examples(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.session_examples_json)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


@lru_cache
def get_settings() -> Settings:
    return Settings()
