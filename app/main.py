"""Entrada principal da API FastAPI."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .config import settings
from .pdf_processor import processar_pdfs
from .models import (
    DataQueryRequest,
    DataQueryResponse,
    HealthResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ProcessPDFsRequest,
    ProcessPDFsResponse,
)
from .search_service import buscar_conhecimento, consultar_dados, formatar_resposta_tecnica
from .security import require_api_key


app = FastAPI(
    title="Auditor Censo Escolar Fundeb",
    version="0.1.0",
    description="API inicial do projeto API-CENSO-FUNDEB.",
)


def _dump_payload(payload: object) -> dict:
    dump_method = getattr(payload, "model_dump", None)
    if callable(dump_method):
        return dump_method()
    dict_method = getattr(payload, "dict", None)
    if callable(dict_method):
        return dict_method()
    return {}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/buscar-conhecimento", response_model=KnowledgeSearchResponse)
def endpoint_buscar_conhecimento(
    payload: KnowledgeSearchRequest,
    _: str = Depends(require_api_key),
) -> KnowledgeSearchResponse:
    try:
        resultados = buscar_conhecimento(payload.pergunta, payload.limite)
        resposta = formatar_resposta_tecnica(payload.pergunta, resultados)
        return KnowledgeSearchResponse(status="ok", resultados=resultados, resposta_tecnica=resposta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/processar-pdfs", response_model=ProcessPDFsResponse)
def endpoint_processar_pdfs(
    payload: ProcessPDFsRequest,
    _: str = Depends(require_api_key),
) -> ProcessPDFsResponse:
    try:
        resultado = processar_pdfs(limit=payload.limit)
        return ProcessPDFsResponse(
            status=resultado.get("status", "ok"),
            processados=resultado.get("processados", 0),
            detalhe=resultado.get("detalhe"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/consultar-dados", response_model=DataQueryResponse)
def endpoint_consultar_dados(
    payload: DataQueryRequest,
    _: str = Depends(require_api_key),
) -> DataQueryResponse:
    try:
        registros = consultar_dados(_dump_payload(payload))
        return DataQueryResponse(status="ok", registros=registros)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "message": "API inicial criada com sucesso.",
    }
