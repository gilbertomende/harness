from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "stage"
    database_url: str = "postgresql+asyncpg://harness:harness@postgres:5432/harness"
    jwt_secret: str = "CHANGE-ME-IN-STAGE"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    admin_username: str = "admin"
    admin_password: str = "change-me"
    default_provider: str = "auto"
    default_model: str = "qwen3:8b"
    ollama_base_url: str = "http://ollama:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_model: str = "qwen3:8b"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-oss-120b"
    router9_base_url: str = "http://host.docker.internal:20128/v1"
    router9_api_key: str = ""
    router9_model: str = ""
    embed_provider: str = "ollama"
    embed_model: str = "nomic-embed-text"
    sandbox_root: str = "/workspace"
    log_level: str = "INFO"
    max_agent_steps: int = 8
    approval_required_for_mutating_tools: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
