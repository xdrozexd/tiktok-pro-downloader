from pathlib import Path
import os
from dataclasses import dataclass

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

# Desktop path
HOME = Path.home()
DEFAULT_OUTPUT_ROOT = HOME / "Desktop" / "TikTokDownloads"

@dataclass
class Settings:
    BASE_DIR: Path = BASE_DIR
    TEMPLATES_DIR: Path = TEMPLATES_DIR
    STATIC_DIR: Path = STATIC_DIR
    DEFAULT_OUTPUT_ROOT: Path = DEFAULT_OUTPUT_ROOT
    YTDLP_CONCURRENCY: int = int(os.getenv("YTDLP_CONCURRENCY", "2"))

settings = Settings()