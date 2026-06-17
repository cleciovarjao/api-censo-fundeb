"""Configuracoes centrais da aplicacao."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - opcional no arranque inicial
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "auditor-censo-escolar-fundeb"
    api_secret_key: str = os.getenv("API_SECRET_KEY", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    default_chunk_size_min: int = 1500
    default_chunk_size_max: int = 2500
    default_chunk_overlap: int = 300


settings = Settings()
