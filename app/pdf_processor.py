"""Leitura, classificacao e persistencia de PDFs do bucket Fundeb."""

from __future__ import annotations

import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz

from .config import settings
from .embeddings import criar_embedding
from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

CLASSIFICACOES = {
    "01_normas_oficiais": {
        "subcategoria": "normas_oficiais",
        "tipo_fonte": "norma_oficial",
        "nivel_autoridade": 1,
    },
    "02_orientacoes_oficiais": {
        "subcategoria": "orientacoes_oficiais",
        "tipo_fonte": "orientacao_oficial",
        "nivel_autoridade": 2,
    },
    "03_estudos_academicos": {
        "subcategoria": "estudos_academicos",
        "tipo_fonte": "estudo_academico",
        "nivel_autoridade": 4,
    },
    "04_materiais_informativos": {
        "subcategoria": "materiais_informativos",
        "tipo_fonte": "material_informativo",
        "nivel_autoridade": 5,
    },
    "05_perguntas_respostas": {
        "subcategoria": "perguntas_respostas",
        "tipo_fonte": "perguntas_respostas",
        "nivel_autoridade": 5,
    },
}


@dataclass(frozen=True)
class TrechoPDF:
    conteudo: str
    pagina: int
    ordem_trecho: int
    tema: str
    tipo_fonte: str
    nivel_autoridade: int


def classificar_caminho_storage(caminho_storage: str) -> Dict[str, Any]:
    caminho_normalizado = caminho_storage.replace("\\", "/").lower()
    for pasta, classificacao in CLASSIFICACOES.items():
        if f"/{pasta.lower()}/" in f"/{caminho_normalizado}/":
            return {
                "categoria": "conhecimento",
                "subcategoria": classificacao["subcategoria"],
                "tipo_fonte": classificacao["tipo_fonte"],
                "nivel_autoridade": classificacao["nivel_autoridade"],
            }

    return {
        "categoria": "conhecimento",
        "subcategoria": "geral",
        "tipo_fonte": "documento_pdf",
        "nivel_autoridade": 5,
    }


def extrair_ano_referencia(caminho_storage: str) -> Optional[int]:
    correspondencia = re.search(r"(19\d{2}|20\d{2})", caminho_storage)
    if correspondencia:
        return int(correspondencia.group(1))
    return None


def extrair_data_publicacao(texto: str) -> Optional[str]:
    if not texto:
        return None
    normalizado = _normalizar_texto(texto)
    match = re.search(r"\b(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})\b", normalizado)
    if match:
        mes = _mapear_mes_pt(match.group(2))
        if mes:
            return f"{match.group(3)}-{mes:02d}-{int(match.group(1)):02d}"
    match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", texto)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def inferir_etapa_do_ciclo(texto_normalizado: str, tipo_fonte: str) -> Optional[str]:
    if not texto_normalizado:
        return None
    if "retific" in texto_normalizado:
        return "retificação"
    if "atualiza" in texto_normalizado or "atualização" in texto_normalizado:
        if "quadrimestre" in texto_normalizado:
            return "atualização quadrimestral"
        return "ajuste"
    if "previs" in texto_normalizado or "estimativa" in texto_normalizado:
        return "estimativa anual" if "anual" in texto_normalizado else "previsão inicial"
    if "coeficiente" in texto_normalizado:
        return "coeficientes de distribuição"
    if "anexo" in texto_normalizado and "calcul" in texto_normalizado:
        return "anexo de cálculo"
    if "complementacao da uniao" in texto_normalizado or "complementação da união" in texto_normalizado:
        return "complementação da União"
    if "publicacao final" in texto_normalizado or "publicação final" in texto_normalizado:
        return "publicação final"
    if tipo_fonte == "orientacao_oficial":
        return "orientação oficial"
    if tipo_fonte == "norma_oficial":
        return "publicação legal"
    return None


def montar_chave_serie_temporal(classificacao: Dict[str, Any], caminho_storage: str, texto_base: str) -> str:
    base = _normalizar_texto(" ".join([Path(caminho_storage).name, caminho_storage, texto_base]))
    if any(token in base for token in ("vaar", "condicionalidade v", "simec", "bncc", "upload", "referencial curricular")):
        return "vaar_condicionalidade_v"
    if any(token in base for token in ("vaaf", "valor anual por aluno")):
        return "vaaf"
    if any(token in base for token in ("vaat", "valor anual total por aluno")):
        return "vaat"
    if any(token in base for token in ("dupla matricula", "dupla matrícula", "aee")):
        return "aee_dupla_matricula"
    if any(token in base for token in ("matricula ponderada", "matrículas ponderadas", "matriculas ponderadas")):
        return "matriculas_ponderadas"
    if any(token in base for token in ("coeficiente", "previsao", "previsão", "estimativa", "atualizacao", "atualização", "retificacao", "retificação")):
        return "fundeb_orcamentario"
    return _normalizar_texto(f"{classificacao['tipo_fonte']} {Path(caminho_storage).name}")


def listar_pdfs_bucket(client: Any, bucket_name: str = "fundeb-conhecimento") -> List[str]:
    bucket = client.storage.from_(bucket_name)
    encontrados: List[str] = []
    visitados: set[str] = set()

    def percorrer(prefixo: str = "") -> None:
        try:
            itens = bucket.list(prefixo or "")
        except Exception as exc:  # pragma: no cover - depende do Supabase
            logger.warning("Nao foi possivel listar '%s': %s", prefixo or "/", exc)
            return

        for item in sorted(itens or [], key=lambda valor: (valor.get("name") or "").lower()):
            nome = (item.get("name") or "").strip()
            if not nome:
                continue

            caminho_completo = f"{prefixo}/{nome}" if prefixo else nome
            chave_normalizada = caminho_completo.replace("\\", "/")
            if chave_normalizada in visitados:
                continue
            visitados.add(chave_normalizada)

            metadata = item.get("metadata")
            if metadata is None and not nome.lower().endswith(".pdf"):
                percorrer(caminho_completo)
                continue

            if nome.lower().endswith(".pdf"):
                encontrados.append(caminho_completo)

    percorrer("")
    return encontrados


def baixar_pdf_temporario(client: Any, bucket_name: str, caminho_storage: str) -> str:
    bucket = client.storage.from_(bucket_name)
    conteudo = bucket.download(caminho_storage)

    if hasattr(conteudo, "content"):
        dados = conteudo.content
    elif hasattr(conteudo, "read"):
        dados = conteudo.read()
    else:
        dados = conteudo

    if isinstance(dados, str):
        dados = dados.encode("utf-8")

    if not isinstance(dados, (bytes, bytearray)):
        raise RuntimeError(f"Nao foi possivel baixar o PDF '{caminho_storage}'.")

    arquivo_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        arquivo_temp.write(dados)
        arquivo_temp.flush()
        return arquivo_temp.name
    finally:
        arquivo_temp.close()


def extrair_texto_pdf(caminho_pdf: str) -> List[Dict[str, Any]]:
    paginas: List[Dict[str, Any]] = []
    documento = fitz.open(caminho_pdf)
    try:
        for numero_pagina, pagina in enumerate(documento, start=1):
            texto = pagina.get_text("text").strip()
            if not texto:
                logger.warning(
                    "Pagina %s sem texto extraivel em '%s'. Possivel OCR necessario.",
                    numero_pagina,
                    os.path.basename(caminho_pdf),
                )
            paginas.append(
                {
                    "pagina": numero_pagina,
                    "texto": texto,
                    "tem_texto": bool(texto),
                }
            )
    finally:
        documento.close()
    return paginas


def dividir_em_trechos(
    texto: str,
    tamanho_minimo: int = 1500,
    tamanho_maximo: int = 2500,
    sobreposicao: int = 300,
) -> List[str]:
    if not texto:
        return []

    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        return []

    trechos: List[str] = []
    inicio = 0
    tamanho_alvo = min(max(tamanho_minimo, 2000), tamanho_maximo)

    while inicio < len(texto):
        fim = min(len(texto), inicio + tamanho_alvo)
        if fim < len(texto):
            janela_maxima = min(len(texto), inicio + tamanho_maximo)
            fim_ideal = texto.rfind(" ", inicio + tamanho_minimo, janela_maxima)
            if fim_ideal == -1:
                fim_ideal = texto.find(" ", fim, janela_maxima)
            if fim_ideal != -1 and fim_ideal > inicio:
                fim = fim_ideal

        trecho = texto[inicio:fim].strip()
        if trecho:
            trechos.append(trecho)

        if fim >= len(texto):
            break

        novo_inicio = max(0, fim - sobreposicao)
        if novo_inicio <= inicio:
            novo_inicio = fim
        inicio = novo_inicio

    return trechos


def _obter_fonte_existente(client: Any, caminho_storage: str) -> Optional[Dict[str, Any]]:
    resposta = (
        client.table("fontes_fundeb")
        .select("id,nome,caminho_storage")
        .eq("caminho_storage", caminho_storage)
        .limit(1)
        .execute()
    )
    dados = resposta.data or []
    return dados[0] if dados else None


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _mapear_mes_pt(mes: str) -> Optional[int]:
    meses = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }
    return meses.get(mes.lower())


def _inserir_fonte(
    client: Any,
    caminho_storage: str,
    bucket_name: str,
    classificacao: Dict[str, Any],
    nome_arquivo: str,
) -> Dict[str, Any]:
    payload = {
        "nome": nome_arquivo,
        "categoria": classificacao["categoria"],
        "subcategoria": classificacao["subcategoria"],
        "tipo_arquivo": "pdf",
        "bucket": bucket_name,
        "caminho_storage": caminho_storage,
        "origem": None,
        "orgao": None,
        "ano_referencia": extrair_ano_referencia(caminho_storage),
        "status": "ativo",
        "nivel_autoridade": classificacao["nivel_autoridade"],
        "observacoes": None,
    }
    resposta = client.table("fontes_fundeb").insert(payload).execute()
    dados = resposta.data or []
    if dados:
        return dados[0]

    fonte_salva = _obter_fonte_existente(client, caminho_storage)
    if not fonte_salva:
        raise RuntimeError(f"Nao foi possivel salvar a fonte '{caminho_storage}'.")
    return fonte_salva


def _resumir_observacoes(mensagens: List[str]) -> Optional[str]:
    mensagens_limpa = [mensagem.strip() for mensagem in mensagens if mensagem.strip()]
    if not mensagens_limpa:
        return None
    return " | ".join(mensagens_limpa)


def processar_pdfs(limit: int = 1, bucket_name: str = "fundeb-conhecimento") -> Dict[str, Any]:
    if limit < 1:
        raise ValueError("limit precisa ser maior ou igual a 1.")

    client = get_supabase_client()
    pdfs = listar_pdfs_bucket(client, bucket_name=bucket_name)
    if not pdfs:
        return {
            "status": "ok",
            "processados": 0,
            "pulados": 0,
            "trechos_criados": 0,
            "avisos": ["Nenhum PDF encontrado no bucket."],
            "arquivos": [],
            "detalhe": "Nenhum PDF encontrado.",
        }

    processados = 0
    pulados = 0
    trechos_criados = 0
    avisos: List[str] = []
    arquivos_processados: List[str] = []

    for caminho_storage in pdfs:
        if processados >= limit:
            break

        if _obter_fonte_existente(client, caminho_storage):
            pulados += 1
            logger.info("Pulando arquivo ja cadastrado: %s", caminho_storage)
            continue

        nome_arquivo = Path(caminho_storage).name
        classificacao = classificar_caminho_storage(caminho_storage)
        observacoes_documento: List[str] = []
        caminho_temporario: Optional[str] = None

        try:
            caminho_temporario = baixar_pdf_temporario(client, bucket_name, caminho_storage)
            paginas = extrair_texto_pdf(caminho_temporario)
            texto_base = " ".join(
                pagina["texto"] for pagina in paginas[:2] if pagina.get("texto")
            )
            data_publicacao = extrair_data_publicacao(texto_base) or extrair_data_publicacao(caminho_storage)
            ano_referencia = extrair_ano_referencia(caminho_storage)
            if not ano_referencia and data_publicacao:
                ano_referencia = int(data_publicacao[:4])
            etapa_do_ciclo = inferir_etapa_do_ciclo(
                _normalizar_texto(f"{texto_base} {caminho_storage}"),
                classificacao["tipo_fonte"],
            )
            serie_temporal_key = montar_chave_serie_temporal(classificacao, caminho_storage, texto_base)
            fonte = _inserir_fonte(client, caminho_storage, bucket_name, classificacao, nome_arquivo)
            fonte_id = fonte.get("id")

            if fonte_id is None:
                raise RuntimeError(f"Fonte criada sem id para '{caminho_storage}'.")

            trechos_para_inserir: List[Dict[str, Any]] = []
            for pagina_info in paginas:
                pagina_numero = pagina_info["pagina"]
                texto_pagina = pagina_info["texto"]
                if not texto_pagina:
                    observacoes_documento.append(
                        f"Pagina {pagina_numero} sem texto extraivel; possivel OCR necessario."
                    )
                    continue

                trechos = dividir_em_trechos(
                    texto_pagina,
                    tamanho_minimo=settings.default_chunk_size_min,
                    tamanho_maximo=settings.default_chunk_size_max,
                    sobreposicao=settings.default_chunk_overlap,
                )

                for ordem_trecho, trecho in enumerate(trechos, start=1):
                    embedding = criar_embedding(trecho)
                    metadados = {
                        "bucket": bucket_name,
                        "caminho_storage": caminho_storage,
                        "nome_arquivo": nome_arquivo,
                        "subcategoria": classificacao["subcategoria"],
                        "tipo_fonte": classificacao["tipo_fonte"],
                        "nivel_autoridade": classificacao["nivel_autoridade"],
                        "pagina": pagina_numero,
                        "ordem_trecho": ordem_trecho,
                        "data_publicacao": data_publicacao,
                        "ano_referencia": ano_referencia,
                        "etapa_do_ciclo": etapa_do_ciclo,
                        "serie_temporal_key": serie_temporal_key,
                    }
                    trechos_para_inserir.append(
                        {
                            "fonte_id": fonte_id,
                            "conteudo": trecho,
                            "pagina": pagina_numero,
                            "ordem_trecho": ordem_trecho,
                            "tema": classificacao["subcategoria"],
                            "tipo_fonte": classificacao["tipo_fonte"],
                            "nivel_autoridade": classificacao["nivel_autoridade"],
                            "ano_referencia": fonte.get("ano_referencia") or ano_referencia,
                            "data_publicacao": data_publicacao,
                            "etapa_do_ciclo": etapa_do_ciclo,
                            "serie_temporal_key": serie_temporal_key,
                            "embedding": embedding,
                            "metadados": metadados,
                        }
                    )

            if trechos_para_inserir:
                client.table("conhecimento_trechos").insert(trechos_para_inserir).execute()
                trechos_criados += len(trechos_para_inserir)
            else:
                observacoes_documento.append("Documento sem texto aproveitavel para gerar trechos.")

            if observacoes_documento:
                observacoes_final = _resumir_observacoes(observacoes_documento)
                client.table("fontes_fundeb").update({"observacoes": observacoes_final}).eq(
                    "id", fonte_id
                ).execute()
                avisos.extend(observacoes_documento)

            processados += 1
            arquivos_processados.append(caminho_storage)
            logger.info("Processado com sucesso: %s", caminho_storage)
        except Exception as exc:
            mensagem = f"Erro ao processar '{caminho_storage}': {exc}"
            logger.exception(mensagem)
            avisos.append(mensagem)
        finally:
            if caminho_temporario and os.path.exists(caminho_temporario):
                try:
                    os.unlink(caminho_temporario)
                except OSError:
                    logger.warning("Nao foi possivel remover arquivo temporario: %s", caminho_temporario)

    return {
        "status": "ok" if processados else "sem_processamento",
        "processados": processados,
        "pulados": pulados,
        "trechos_criados": trechos_criados,
        "arquivos": arquivos_processados,
        "avisos": avisos,
        "detalhe": "Processamento concluido.",
    }
