from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    app_name: str = "AI-Powered PPTX Creator"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    
    # API Keys
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    pexels_api_key: str = Field(default="", env="PEXELS_API_KEY")
    unsplash_access_key: str = Field(default="", env="UNSPLASH_ACCESS_KEY")
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    
    # Limits
    max_slides: int = Field(default=50, env="MAX_SLIDES")
    upload_max_size_mb: int = Field(default=50, env="UPLOAD_MAX_SIZE_MB")
    
    # Directories
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    temp_dir: str = "./temp"
    template_dir: str = Field(default="./templates", env="TEMPLATE_DIR")
    
    # Image settings
    default_image_source: str = Field(default="unsplash", env="DEFAULT_IMAGE_SOURCE")
    image_generation_model: str = Field(default="dall-e-3", env="IMAGE_GENERATION_MODEL")
    
    # Pydantic v2 config
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in .env
    )

def get_settings() -> Settings:
    """Get settings instance"""
    return Settings()

def create_directories():
    """Create necessary directories"""
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.temp_dir, exist_ok=True)
    os.makedirs(settings.template_dir, exist_ok=True)
