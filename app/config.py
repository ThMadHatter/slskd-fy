import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    SLSKD_API_URL: str = "http://localhost:5030/api/v0"
    SLSKD_API_KEY: str = "your-slskd-api-key"

    # Path configuration from environment variables
    MUSIC_LIBRARY_PATH: str = "/music"
    UPLOADS_PATH: str = "/uploads"
    SINGLES_PATH: str = "/uploads/Singles"
    DOWNLOADS_PATH: str = "/downloads"

    # SQLite Database connection string
    DATABASE_URL: str = "sqlite:///track_portal.db"

    # Secret key for JWT cookie sessions
    SECRET_KEY: str = "supersecretkey_change_me_in_production"

    # Default admin credentials
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""

    # Navidrome settings
    NAVIDROME_URL: str = "http://localhost:4533"
    NAVIDROME_USER: str = "admin"
    NAVIDROME_PASSWORD: str = ""
    NAVIDROME_TOKEN: str = ""
    NAVIDROME_SALT: str = ""

    # Optional integrations URLs (e.g. FileBrowser, Navidrome UI, etc)
    FILEBROWSER_URL: str = "" # URL to link to FileBrowser
    NAVIDROME_UI_URL: str = "" # URL to link to Navidrome UI

    # Configurable download quality ranking
    # The user asked for quality ranking order: FLAC, ALAC, WAV, AAC, MP3 320, MP3 V0, everything else
    # Let's specify it as a comma-separated list of formats
    QUALITY_RANKING: str = "flac,alac,wav,aac,mp3_320,mp3_v0"

    # Search strategy configuration
    # Can be STRICT, BALANCED, or AGGRESSIVE
    SEARCH_STRATEGY: str = "BALANCED"

settings = Settings()
