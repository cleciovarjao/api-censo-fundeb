"""Funcoes de embeddings da aplicacao."""

from __future__ import annotations

from typing import List

from .config import settings


def criar_embedding(texto: str) -> List[float]:
    """Gera embedding com OpenAI usando o modelo do briefing."""

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY precisa estar configurada no .env.")

    texto = texto.strip()
    if not texto:
        raise ValueError("O texto informado para embedding esta vazio.")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depende de instalacao
        raise RuntimeError("Pacote openai nao esta instalado.") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texto,
    )
    return list(response.data[0].embedding)
