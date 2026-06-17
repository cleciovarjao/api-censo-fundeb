"""Seguranca simples por chave de API."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="x-api-key")) -> str:
    if not settings.api_secret_key:
        return x_api_key or ""

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header x-api-key ausente.",
        )

    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chave de API invalida.",
        )

    return x_api_key
