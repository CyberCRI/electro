"""Settings for the `electro` Framework."""

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from .toolkit.images_storage.storages_enums import StoragesIDs


class Settings(BaseSettings):
    """Settings for the project."""

    model_config = SettingsConfigDict(
        env_prefix="ELECTRO__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    LOCALES_PATH: str = "locales"  # Relative to the current working directory
    DEFAULT_LOCALE: str = "en"  # Should mirror the `BOT_LANGUAGE` setting. User in the `make upload-locales` target

    DO_USE_FILE_LOGS: bool = True
    DO_USE_COMMAND_ALIASES: bool = False

    # Bot settings
    BOT_COMMAND_PREFIX: str = "!"
    BOT_LANGUAGE: str = "en"  # Should mirror the `DEFAULT_LOCALE` setting. User in the Python code

    # Postgres database credentials
    DATABASE_URL: PostgresDsn | None = None
    # if the `DATABASE_URL` is not set, then use the following credentials:
    POSTGRES_HOST: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_PORT: int | None = 5432
    POSTGRES_DB: str | None = None

    ENABLE_DATABASE_SSL: bool = True

    # Redis credentials
    REDIS_URL: RedisDsn | None = None
    # if the `REDIS_URL` is not set, then use the following credentials:
    REDIS_HOST: str | None = None
    REDIS_PORT: int | None = 6379
    REDIS_DB: int | None = 0

    # Images storage
    STORAGE_SERVICE_ID: StoragesIDs = "S3"

    # S3 storage
    # Allow this to be optional
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION_NAME: str | None = None

    S3_IMAGES_BUCKET_NAME: str = "files"

    # Azure Blob Storage
    # NB: It appears to be never used directly, rather the env vars are used by `DefaultAzureCredential`
    AZURE_CLIENT_ID: str | None = None
    AZURE_TENANT_ID: str | None = None
    AZURE_CLIENT_SECRET: str | None = None

    AZURE_STORAGE_ACCOUNT_NAME: str | None = None

    AZURE_CONTAINER_NAME: str = "files"

    HTTPX_CLIENT_DEFAULT_TIMEOUT: int = 60

    # TODO: [06.03.2024 by Mykola] Do not let it be `None`. It's `None` only because we want to let `spinx` import it
    #  while building the documentation.
    OPENAI_API_KEY: str | None = "sk_test_1234567890"

    OPENAI_CHAT_COMPLETION_MODEL: str = "gpt-4o"
    OPENAI_DALLE_MODEL: str = "dall-e-3"

    DEFAULT_SLEEP_TIME: int = 3  # seconds
    SLEEP_TIME_PER_CHARACTER: float = 0.05

    MESSAGE_BREAK: str = "--- message break ---"
    MESSAGE_SLEEP_INSTRUCTION_PATTERN: str = r"--- sleep (\d+.?\d*) seconds ---"

    MESSAGE_MAX_LENGTH: int = 1900  # 2000 - 100 (safe margin)

    GO_BACK_COMMAND: str = "_go_back"
    RELOAD_COMMAND: str = "_reload"

    # Validate GO_BACK_COMMAND
    if GO_BACK_COMMAND.startswith(BOT_COMMAND_PREFIX):
        raise ValueError(
            f"The GO_BACK_COMMAND ({GO_BACK_COMMAND}) "
            f"should not start with the BOT_COMMAND_PREFIX ({BOT_COMMAND_PREFIX})"
        )

    # Validate RELOAD_COMMAND
    if RELOAD_COMMAND.startswith(BOT_COMMAND_PREFIX):
        raise ValueError(
            f"The RELOAD_COMMAND ({RELOAD_COMMAND}) "
            f"should not start with the BOT_COMMAND_PREFIX ({BOT_COMMAND_PREFIX})"
        )


settings = Settings()
