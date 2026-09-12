from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    app_name: str = "Smart Literacy Stewardship"
    app_version: str = "2.0.0"
    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_environment_value(cls, value: object) -> object:
        """Tolerate common host build-mode values that collide with DEBUG."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"debug", "development", "dev"}:
                return True
        return value

    mysql_host: str
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str
    mysql_database: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 2
    research_storage_root: Path = (
        Path(__file__).resolve().parents[2] / "storage" / "research"
    )
    knowledge_base_root: Path = BACKEND_ROOT / "data" / "knowledge_bases"
    knowledge_base_chunk_size: int = 1000
    knowledge_base_chunk_overlap: int = 120
    knowledge_base_retrieval_candidate_k: int = 10
    knowledge_base_retrieval_top_k: int = 5
    knowledge_base_rrf_k: int = 60
    embedding_provider: str = "openai_compatible"
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_timeout_seconds: float = 60.0
    aliyun_embedding_provider: str | None = None
    aliyun_embedding_api_key: str | None = None
    aliyun_embedding_url: str | None = None
    aliyun_embedding_model: str = "qwen3.7-text-embedding-flash"
    aliyun_embedding_dimension: int = 1024
    aliyun_embedding_batch_size: int = 25
    aliyun_embedding_timeout_seconds: float = 60.0
    xfyun_embedding_app_id: str | None = None
    xfyun_embedding_api_key: str | None = None
    xfyun_embedding_api_secret: str | None = None
    xfyun_embedding_url: str = "https://emb-cn-huabei-1.xf-yun.com/"
    xfyun_embedding_dimension: int = 2560
    xfyun_embedding_max_concurrency: int = 4
    xfyun_embedding_max_payload_bytes: int = 2048
    xfyun_embedding_uid: str | None = None

    llm_provider: str = "mock"
    spark_api_key: str | None = None
    spark_api_base: str = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    spark_model_id: str = "spark-x2.5-4b"
    spark_lora_id: str | None = None
    spark_max_tokens: int = 8192
    spark_resource_max_tokens: int = 8192
    spark_resource_retry_max_tokens: int = 16384
    spark_research_analysis_max_tokens: int = 4096
    spark_research_analysis_model_id: str = "spark-x2.5-1.7b"
    spark_timeout_seconds: float = 120.0

    # Assistant credentials deliberately do not reuse the OpenAI-compatible
    # Spark configuration above: course design must remain on that provider.
    research_agent_provider: str | None = None
    spark_assistant_app_id: str | None = None
    spark_assistant_api_key: str | None = None
    spark_assistant_api_secret: str | None = None
    research_agent_url: str | None = None
    research_agent_domain: str = "generalv3.5"
    research_agent_timeout_seconds: float = 120.0
    research_analysis_max_chunks: int = 4
    research_analysis_max_context_chars: int = 4500

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self):
        return (
            f"mysql+pymysql://{self.mysql_user}:"
            f"{self.mysql_password}@"
            f"{self.mysql_host}:"
            f"{self.mysql_port}/"
            f"{self.mysql_database}"
            "?charset=utf8mb4"
        )


settings = Settings()
