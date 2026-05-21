from pydantic_settings import BaseSettings, SettingsConfigDict




class Settings(BaseSettings):
    """환경변수(.env) 기반 애플리케이션 설정"""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "RAG Document Analyzer"
    allowed_extensions: str = ".hwp,.hwpx,.pdf,.docx,.ppt,.pptx"
    upload_dir: str = "./data/uploads"
    work_dir: str = "./data/work"
    chroma_dir: str = "./data/chroma_db"
    ocr_output_dir: str = "./data/ocr_output"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_sec: int = 300
    hwp_extract_bin: str = "hwp-extract"
    hwp_extract_args: str = ""
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_prefix_mode: str = "bge"  # bge | e5 | none
    database_url: str = ""

    @property
    def allowed_ext_set(self) -> set[str]:
        """허용 확장자를 set 형태로 변환한 것"""
        return {e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()}


settings = Settings()
