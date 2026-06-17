"""Cliente Supabase usado pela aplicacao."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Any:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar configurados no .env."
        )

    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover - depende de instalacao
        raise RuntimeError("Pacote supabase nao esta instalado.") from exc

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
