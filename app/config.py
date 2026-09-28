from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "none"
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen3.5:9b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ocr_enabled: bool = True
    template_path: Path = ROOT_DIR / "samples" / "Template_Biaya_KL26052203866176.xlsx"
    max_chars_for_llm: int = 24_000
    llm_timeout_seconds: float = 60.0
    pdf_scan_text_threshold: int = 40
    vision_enabled: bool = True
    vision_provider: str = "ollama"
    vision_model: str = "qwen3-vl:8b-instruct"
    vision_timeout_seconds: float = 180.0
    vision_max_pages: int = 100
    vision_render_scale: float = 1.5
    vision_jpeg_quality: int = 85
    vision_page_batch_size: int = 4
    vision_thumbnail_scale: float = 0.6
    vision_thumbnail_width: int = 600
    vision_context_size: int = 32768
    vision_max_output_tokens: int = 8192
    vision_worker_urls: str = ""
    vision_parallel_requests: int = 2
    vision_classify_scale: float = 0.6
    vision_classify_context_size: int = 8192
    vision_classify_max_output_tokens: int = 256
    vision_min_detail_lines: int = 20
    agreements_db_path: Path = ROOT_DIR / "data" / "agreements.db"


settings = Settings()
