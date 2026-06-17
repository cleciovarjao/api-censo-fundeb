"""Modelos de entrada e saida da API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "auditor-censo-escolar-fundeb"


class KnowledgeSearchRequest(BaseModel):
    pergunta: str = Field(min_length=1, description="Texto da pergunta do usuario.")
    limite: int = Field(default=8, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    conteudo: str
    pagina: Optional[int] = None
    nome: Optional[str] = None
    caminho_storage: Optional[str] = None
    tipo_fonte: Optional[str] = None
    nivel_autoridade: Optional[int] = None
    similarity: Optional[float] = None
    final_score: Optional[float] = None
    referencia_tecnica_formatada: Optional[str] = None
    nome_real_fonte: Optional[str] = None
    tipo_documento: Optional[str] = None
    orgao: Optional[str] = None
    numero_norma: Optional[str] = None
    ano_norma: Optional[int] = None
    artigo: Optional[str] = None
    paragrafo: Optional[str] = None
    inciso: Optional[str] = None
    item: Optional[str] = None
    secao: Optional[str] = None
    titulo_secao: Optional[str] = None
    data_publicacao: Optional[str] = None
    ano_referencia: Optional[int] = None
    vigencia_inicio: Optional[str] = None
    vigencia_fim: Optional[str] = None
    etapa_do_ciclo: Optional[str] = None
    serie_temporal_key: Optional[str] = None
    versao_temporal: Optional[str] = None
    metadados: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    status: str
    resultados: List[KnowledgeSearchResult] = Field(default_factory=list)
    resposta_tecnica: Optional[str] = None
    detalhe: Optional[str] = None


class ProcessPDFsRequest(BaseModel):
    limit: int = Field(default=1, ge=1, le=100)


class ProcessPDFsResponse(BaseModel):
    status: str
    processados: int = 0
    detalhe: Optional[str] = None


class DataQueryRequest(BaseModel):
    consulta: Optional[str] = None
    municipio: Optional[str] = None
    ano_referencia: Optional[int] = None
    limite: int = Field(default=20, ge=1, le=100)


class DataQueryResponse(BaseModel):
    status: str
    registros: List[Dict[str, Any]] = Field(default_factory=list)
    detalhe: Optional[str] = None
