"""Servicos de busca vetorial e consulta de dados."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from .embeddings import criar_embedding
from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

TECH_TERMS = {
    "vaar",
    "vaaf",
    "vaat",
    "aee",
    "bncc",
    "simec",
    "upload",
    "ato de aprovacao",
    "ato de aprovação",
    "referencial curricular",
    "condicionalidade v",
    "documentos exigidos",
}

QUERY_BOOST_TERMS = {
    "documentos exigidos": 0.18,
    "condicionalidade v": 0.20,
    "vaar": 0.16,
    "vaaf": 0.12,
    "vaat": 0.12,
    "aee": 0.10,
    "bncc": 0.18,
    "simec": 0.18,
    "upload": 0.12,
    "ato de aprovacao": 0.18,
    "referencial curricular": 0.18,
}

CONTENT_TECH_BOOST = {
    "simec": 0.18,
    "upload": 0.14,
    "bncc": 0.16,
    "ato de aprovacao": 0.16,
    "referencial curricular": 0.16,
    "condicionalidade v": 0.20,
    "vaar": 0.12,
    "vaaf": 0.10,
    "vaat": 0.10,
    "aee": 0.08,
}


def buscar_conhecimento(pergunta: str, limite: int = 8) -> List[Dict[str, Any]]:
    if limite < 1:
        raise ValueError("limite precisa ser maior ou igual a 1.")

    client = get_supabase_client()
    embedding = criar_embedding(pergunta)
    pergunta_normalizada = _normalizar_texto(pergunta)
    intencao_temporal = _eh_intencao_temporal(pergunta_normalizada)
    candidato_limite = max(limite * (6 if intencao_temporal else 4), 30 if intencao_temporal else 20)

    resposta = client.rpc(
        "match_conhecimento_trechos",
        {"query_embedding": embedding, "match_count": candidato_limite},
    ).execute()

    resultados = list(resposta.data or [])

    resultados = [_enriquecer_resultado(item, pergunta_normalizada) for item in resultados]
    resultados = _marcar_versoes_temporais(resultados, intencao_temporal)
    resultados.sort(
        key=lambda item: (
            -(item.get("final_score") if item.get("final_score") is not None else 0.0),
            item.get("nivel_autoridade") if item.get("nivel_autoridade") is not None else 999,
            -(item.get("similarity") if item.get("similarity") is not None else 0.0),
        )
    )

    saida: List[Dict[str, Any]] = []
    for item in resultados[:limite]:
        metadados = item.get("metadados") or {}
        if isinstance(metadados, str):
            try:
                metadados = json.loads(metadados)
            except json.JSONDecodeError:
                metadados = {"valor_bruto": metadados}

        referencia = _construir_referencia_tecnica(item, metadados)

        saida.append(
            {
                "conteudo": item.get("conteudo"),
                "pagina": item.get("pagina"),
                "nome": metadados.get("nome_arquivo"),
                "caminho_storage": metadados.get("caminho_storage"),
                "tipo_fonte": item.get("tipo_fonte"),
                "nivel_autoridade": item.get("nivel_autoridade"),
                "similarity": item.get("similarity"),
                "final_score": item.get("final_score"),
                "nome_real_fonte": referencia.get("nome_real_fonte"),
                "tipo_documento": referencia.get("tipo_documento"),
                "orgao": referencia.get("orgao"),
                "numero_norma": referencia.get("numero_norma"),
                "ano_norma": referencia.get("ano_norma"),
                "artigo": referencia.get("artigo"),
                "paragrafo": referencia.get("paragrafo"),
                "inciso": referencia.get("inciso"),
                "item": referencia.get("item"),
                "secao": referencia.get("secao"),
                "titulo_secao": referencia.get("titulo_secao"),
                "referencia_tecnica_formatada": referencia.get("referencia_tecnica_formatada"),
                "data_publicacao": item.get("data_publicacao"),
                "ano_referencia": item.get("ano_referencia"),
                "vigencia_inicio": item.get("vigencia_inicio"),
                "vigencia_fim": item.get("vigencia_fim"),
                "etapa_do_ciclo": item.get("etapa_do_ciclo"),
                "serie_temporal_key": item.get("serie_temporal_key"),
                "versao_temporal": item.get("versao_temporal"),
                "metadados": metadados,
            }
        )

    return saida


def formatar_resposta_tecnica(pergunta: str, resultados: List[Dict[str, Any]]) -> str:
    if not resultados:
        return _montar_resposta_sem_base(pergunta)

    top1 = resultados[0]
    top2 = resultados[1] if len(resultados) > 1 else None
    top3 = resultados[2] if len(resultados) > 2 else None

    fontes_formatadas = []
    for item in resultados[:3]:
        referencia = _extrair_referencia_do_item(item)
        nome_referencia = referencia.get("referencia_tecnica_formatada") or referencia.get("nome_real_fonte") or "Fonte não identificada"
        tipo_fonte = item.get("tipo_fonte") or "n/d"
        nivel = item.get("nivel_autoridade")
        fontes_formatadas.append(
            f"- Fonte: {nome_referencia}\n"
            f"  Tipo de fonte: {tipo_fonte}\n"
            f"  Nível de autoridade: {nivel if nivel is not None else 'n/d'}\n"
            f"  Data de publicação: {item.get('data_publicacao') or 'n/d'}\n"
            f"  Ano de referência: {item.get('ano_referencia') or 'n/d'}\n"
            f"  Vigência: { _formatar_vigencia(item.get('vigencia_inicio'), item.get('vigencia_fim')) }\n"
            f"  Etapa do ciclo: {item.get('etapa_do_ciclo') or 'n/d'}\n"
            f"  Versão temporal: {item.get('versao_temporal') or 'n/d'}\n"
            f"  Observação técnica: {referencia.get('observacao_tecnica') or 'n/d'}"
        )

    comparativo_temporal = _montar_comparativo_temporal(pergunta, resultados)
    resposta_tecnica = _montar_resposta_tecnica(pergunta, top1, top2, top3)
    fundamentacao = _montar_fundamentacao(top1, top2, top3)
    analise = _montar_analise_tecnica(pergunta, top1, top2, top3)
    providencias = _montar_providencias(pergunta, top1, top2, top3)
    riscos = _montar_riscos(pergunta, top1, top2, top3)

    bloco_fontes = "\n".join(fontes_formatadas)
    titulo = _gerar_titulo_tecnico(pergunta, top1)
    bloco_comparativo = f"{comparativo_temporal}\n\n" if comparativo_temporal else ""

    return (
        f"{titulo}\n\n"
        f"1. Resposta técnica\n"
        f"{resposta_tecnica}\n\n"
        f"{bloco_comparativo}"
        f"2. Fundamentação encontrada na base\n"
        f"{fundamentacao}\n\n"
        f"3. Análise técnica\n"
        f"{analise}\n\n"
        f"4. Providências recomendadas\n"
        f"{providencias}\n\n"
        f"5. Riscos de inconsistência\n"
        f"{riscos}\n\n"
        f"6. Fontes consultadas\n"
        f"{bloco_fontes}"
    )


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _contar_ocorrencias(texto: str, termo: str) -> int:
    if not texto or not termo:
        return 0
    padrao = r"\b" + re.escape(termo) + r"\b"
    return len(re.findall(padrao, texto))


def _pontuar_resultado(item: Dict[str, Any], pergunta_normalizada: str) -> float:
    conteudo = _normalizar_texto(str(item.get("conteudo") or ""))
    metadados = item.get("metadados") or {}
    if isinstance(metadados, str):
        try:
            metadados = json.loads(metadados)
        except json.JSONDecodeError:
            metadados = {"valor_bruto": metadados}

    nome_arquivo = _normalizar_texto(str(metadados.get("nome_arquivo") or item.get("nome") or ""))
    caminho_storage = _normalizar_texto(str(metadados.get("caminho_storage") or item.get("caminho_storage") or ""))
    tipo_fonte = _normalizar_texto(str(item.get("tipo_fonte") or ""))
    texto_completo = " ".join([conteudo, nome_arquivo, caminho_storage, tipo_fonte])

    similarity = float(item.get("similarity") or 0.0)
    nivel_autoridade = item.get("nivel_autoridade")
    nivel_autoridade = int(nivel_autoridade) if nivel_autoridade is not None else 9

    score = similarity * 0.68
    score += max(0.0, (6 - min(nivel_autoridade, 6))) * 0.045

    consulta_sem_acento = _normalizar_texto(pergunta_normalizada)
    for termo, peso in QUERY_BOOST_TERMS.items():
        if termo in consulta_sem_acento:
            if termo in texto_completo:
                score += peso

    if any(termo in consulta_sem_acento for termo in ("documentos exigidos", "condicionalidade v", "vaar", "bncc", "simec", "referencial curricular")):
        if any(termo in texto_completo for termo in ("simec", "upload", "bncc", "ato de aprovacao", "referencial curricular", "condicionalidade v")):
            score += 0.22

    if any(termo in consulta_sem_acento for termo in ("vaar", "vaaf", "vaat")) and any(termo in texto_completo for termo in ("vaar", "vaaf", "vaat")):
        score += 0.12

    conteudo_normalizado = _normalizar_texto(str(item.get("conteudo") or ""))
    ocorrencias_exatas = 0
    for termo in {
        token
        for token in pergunta_normalizada.split()
        if len(token) >= 4
    }:
        ocorrencias_exatas += _contar_ocorrencias(conteudo_normalizado, termo)
    score += min(ocorrencias_exatas, 12) * 0.015

    tech_hits = 0
    for termo in TECH_TERMS:
        if termo in texto_completo:
            tech_hits += 1
    score += min(tech_hits, 8) * 0.02

    if "norma_oficial" == tipo_fonte:
        score += 0.06
    elif "orientacao_oficial" == tipo_fonte:
        score += 0.05
    elif "estudo_academico" == tipo_fonte:
        score += 0.02
    elif "material_informativo" == tipo_fonte:
        score += 0.01

    return round(score, 6)


def _enriquecer_resultado(item: Dict[str, Any], pergunta_normalizada: str) -> Dict[str, Any]:
    item = dict(item)
    item["final_score"] = _pontuar_resultado(item, pergunta_normalizada)
    item.update(_extrair_metadados_temporais(item))
    return item


def _gerar_titulo_tecnico(pergunta: str, top1: Dict[str, Any]) -> str:
    pergunta_normalizada = _normalizar_texto(pergunta)
    if any(termo in pergunta_normalizada for termo in ("condicionalidade v", "vaar", "simec", "documentos exigidos", "referencial curricular", "upload")):
        return "ANÁLISE TÉCNICA DA CONDICIONALIDADE V DO VAAR"
    if "aee" in pergunta_normalizada or "dupla matricula" in pergunta_normalizada:
        return "ANÁLISE TÉCNICA SOBRE DUPLA MATRÍCULA NO AEE"
    if "vaaf" in pergunta_normalizada:
        return "ANÁLISE TÉCNICA DA COMPLEMENTAÇÃO-VAAF NO FUNDEB"
    if "fundeb" in pergunta_normalizada:
        return "ANÁLISE TÉCNICA SOBRE FUNDEB E SUA FINALIDADE"
    tipo_fonte = top1.get("tipo_fonte") or "documento técnico"
    return f"ANÁLISE TÉCNICA COM BASE EM {tipo_fonte.upper()}"


def _fragmento_relevante(item: Dict[str, Any]) -> str:
    conteudo = str(item.get("conteudo") or "").strip()
    if not conteudo:
        return "A base consultada não trouxe trecho textual suficiente para detalhamento."
    if len(conteudo) <= 420:
        return conteudo
    return conteudo[:420].rsplit(" ", 1)[0].strip() + "..."


def _montar_resposta_tecnica(pergunta: str, top1: Dict[str, Any], top2: Optional[Dict[str, Any]], top3: Optional[Dict[str, Any]]) -> str:
    trecho1 = _fragmento_relevante(top1)
    tipo = top1.get("tipo_fonte") or "n/d"
    nivel = top1.get("nivel_autoridade")
    if _base_insuficiente(top1, top2, top3):
        return (
            "A base atualmente indexada não reúne evidência documental suficiente para sustentar conclusão técnica segura. "
            "O material recuperado indica apenas proximidade temática, sem lastro bastante para afirmar obrigação, procedimento, percentual, prazo ou exigência documental com segurança auditável."
        )

    if any(termo in _normalizar_texto(pergunta) for termo in ("documentos exigidos", "condicionalidade v", "vaar", "simec", "referencial curricular", "upload")):
        return (
            "A Condicionalidade V do VAAR exige comprovação documental da rede com base em critérios operacionais definidos na orientação oficial e no fundamento legal do Fundeb. "
            f"Na base consultada, os pontos verificáveis aparecem associados a {', '.join(_termos_encontrados_no_texto(top1, ['simec', 'upload', 'bncc', 'referencial curricular', 'ato de aprovacao', 'condicionalidade v'])) or 'comprovação documental'}, o que indica três exigências práticas: cumprir os critérios descritos na fonte, usar o meio correto de envio ou registro e manter a evidência validada no fluxo adequado. "
            "Na prática, a Secretaria deve conferir quais documentos a fonte pede, identificar como a comprovação deve ser apresentada e somente registrar conformidade quando a evidência anexada demonstrar aderência ao requisito operacional."
        )

    if "aee" in _normalizar_texto(pergunta) or "dupla matricula" in _normalizar_texto(pergunta):
        return (
            "A base normativa consultada fixa o fundamento legal da dupla matrícula no AEE para as hipóteses autorizadas, especialmente quando se trata de estudante da educação regular da rede pública que recebe atendimento educacional especializado. "
            "Isso não autoriza ampliação da regra nem contagem fora das hipóteses legais; ao contrário, delimita o enquadramento correto para o Censo Escolar e para o financiamento. "
            f"O trecho mais relevante veio de fonte {tipo} (nível {nivel}) e reforça que o registro do AEE deve permanecer estritamente aderente à regra legal."
        )

    if "vaaf" in _normalizar_texto(pergunta):
        return (
            "A complementação-VAAF é distribuída com base no valor anual mínimo por aluno definido nacionalmente e segundo os critérios legais do Fundeb. "
            "A leitura técnica deve permanecer fiel ao texto normativo e à orientação operacional, sem extrapolar a lógica de cálculo para além do que a base consultada permite afirmar. "
            f"O trecho recuperado da base ({tipo}, nível {nivel}) mostra a parametrização do cálculo e sua relação direta com o VAAF-MIN."
        )

    if "fundeb" in _normalizar_texto(pergunta):
        return (
            "O Fundeb é o mecanismo central de financiamento da educação básica pública e organiza a redistribuição de recursos sob critérios legais e finalidades específicas. "
            "Na gestão pública, a leitura correta exige aderência à norma oficial e às orientações complementares, sem transformar texto explicativo em obrigação autônoma. "
            f"O trecho mais relevante recuperado ({tipo}, nível {nivel}) mostra o enquadramento normativo do fundo e a sua finalidade de uso."
        )

    return (
        f"Com base no trecho recuperado ({tipo}, nível {nivel}), a resposta técnica deve ser lida estritamente a partir do conteúdo recuperado, sem extrapolar o alcance da base: {trecho1}"
    )


def _montar_fundamentacao(top1: Dict[str, Any], top2: Optional[Dict[str, Any]], top3: Optional[Dict[str, Any]]) -> str:
    partes = []
    for item in [top1, top2, top3]:
        if not item:
            continue
        referencia = _extrair_referencia_do_item(item)
        nome = referencia.get("referencia_tecnica_formatada") or referencia.get("nome_real_fonte") or "Fonte não identificada"
        tipo = item.get("tipo_fonte") or "n/d"
        nivel = item.get("nivel_autoridade")
        trecho = _fragmento_relevante(item)
        partes.append(
            f"- {nome} ({tipo}, nível {nivel if nivel is not None else 'n/d'}): {trecho}"
        )
    return "\n".join(partes)


def _montar_analise_tecnica(pergunta: str, top1: Dict[str, Any], top2: Optional[Dict[str, Any]], top3: Optional[Dict[str, Any]]) -> str:
    pergunta_normalizada = _normalizar_texto(pergunta)
    if any(termo in pergunta_normalizada for termo in ("documentos exigidos", "condicionalidade v", "vaar", "simec", "referencial curricular", "upload")):
        return (
            "Do ponto de vista da Secretaria Municipal de Educação e da equipe responsável pela comprovação, o ponto decisivo é verificar quais critérios a fonte exige, por qual meio a comprovação deve ser apresentada e em qual fluxo isso precisa ser validado. "
            "Quando a pergunta envolve Condicionalidade V, VAAR, Simec, upload, BNCC, ato de aprovação ou referencial curricular, a checagem deve confrontar o documento anexado com o requisito descrito na nota técnica e com o fundamento normativo que sustenta a exigência."
        )
    if "aee" in pergunta_normalizada or "dupla matricula" in pergunta_normalizada:
        return (
            "Na prática escolar e na Secretaria, o ponto crítico é evitar contagem indevida e garantir que a matrícula dupla ocorra somente nas hipóteses autorizadas. "
            "Esse cuidado afeta simultaneamente o Censo Escolar, a apuração de matrículas e a leitura correta da base de financiamento."
        )
    if "vaaf" in pergunta_normalizada:
        return (
            "A complementação-VAAF exige leitura coordenada entre a regra legal de cálculo e a base de matrículas ponderadas. "
            "Para a gestão municipal, a atenção deve recair sobre o parâmetro utilizado, porque qualquer divergência na base numérica repercute diretamente na distribuição de recursos."
        )
    if "fundeb" in pergunta_normalizada:
        return (
            "A finalidade do Fundeb é financiar a educação básica por meio de redistribuição orientada por regras legais. "
            "Na gestão, isso significa acompanhar corretamente o uso dos recursos, manter aderência à finalidade legal e evitar interpretações amplas que ultrapassem a base normativa."
        )
    return "A base consultada sustenta a leitura técnica, mas a conclusão deve permanecer limitada ao conteúdo efetivamente recuperado, sem extrapolar a fonte."


def _montar_providencias(pergunta: str, top1: Dict[str, Any], top2: Optional[Dict[str, Any]], top3: Optional[Dict[str, Any]]) -> str:
    pergunta_normalizada = _normalizar_texto(pergunta)
    if any(termo in pergunta_normalizada for termo in ("documentos exigidos", "condicionalidade v", "vaar", "simec", "referencial curricular", "upload")):
        return (
            "- Conferir no Simec quais documentos foram efetivamente enviados e em qual situação de validação se encontram.\n"
            "- Verificar se o upload corresponde ao documento esperado pela orientação técnica.\n"
            "- Identificar, na própria fonte consultada, quais critérios precisam ser atendidos para a Condicionalidade V.\n"
            "- Cruzar o conteúdo do documento com BNCC, ato de aprovação e referencial curricular, quando esses elementos constarem da base consultada.\n"
            "- Registrar a divergência se a evidência anexada não corresponder ao requisito operacional descrito na nota técnica."
        )
    if "aee" in pergunta_normalizada or "dupla matricula" in pergunta_normalizada:
        return (
            "- Validar se a matrícula dupla está enquadrada na hipótese legal do AEE.\n"
            "- Conferir se a escola registrou corretamente a situação no Censo Escolar.\n"
            "- Revisar a documentação do atendimento especializado para impedir dupla contagem indevida."
        )
    if "vaaf" in pergunta_normalizada:
        return (
            "- Conferir os parâmetros usados no cálculo do VAAF-MIN.\n"
            "- Revisar a base de matrículas ponderadas.\n"
            "- Validar se os dados oficiais da rede estão consistentes com a regra de distribuição e com a base consultada."
        )
    if "fundeb" in pergunta_normalizada:
        return (
            "- Confirmar a leitura da finalidade legal do fundo na norma oficial.\n"
            "- Usar a base normativa como referência principal e as orientações como suporte operacional.\n"
            "- Evitar extrapolar o texto além da regra formal ou transformar explicação em obrigação autônoma."
        )
    return "- Revisar o trecho consultado e validar o documento de origem antes de aplicar qualquer decisão."


def _montar_riscos(pergunta: str, top1: Dict[str, Any], top2: Optional[Dict[str, Any]], top3: Optional[Dict[str, Any]]) -> str:
    pergunta_normalizada = _normalizar_texto(pergunta)
    if any(termo in pergunta_normalizada for termo in ("documentos exigidos", "condicionalidade v", "vaar", "simec", "referencial curricular", "upload")):
        return (
            "O principal risco é converter orientação operacional em obrigação legal autônoma sem checar a norma oficial correspondente. "
            "Há também risco de glosa, reprovação da condicionalidade, inconsistência de comprovação ou questionamento em controle interno se o upload no sistema não refletir exatamente o documento ou a evidência requerida. "
            "Quando a fonte mencionar critérios específicos, eles devem ser observados como condição real de atendimento e não como sugestão genérica."
        )
    if "aee" in pergunta_normalizada or "dupla matricula" in pergunta_normalizada:
        return (
            "O risco central é contabilizar estudante fora das hipóteses legais e distorcer o Censo Escolar ou a distribuição de recursos. "
            "Se a matrícula dupla não estiver corretamente enquadrada, pode haver inconsistência de registro e fragilidade na justificativa do atendimento especializado."
        )
    if "vaaf" in pergunta_normalizada:
        return (
            "O risco principal é usar base de cálculo incorreta ou desatualizada, com efeito direto sobre a distribuição de recursos do Fundeb."
        )
    if "fundeb" in pergunta_normalizada:
        return (
            "O risco é ampliar a finalidade do fundo além do que a norma permite ou interpretar o texto sem respeitar a hierarquia correta das fontes."
        )
    return "Sem trecho suficiente, o risco é concluir além da base documental recuperada."


def _base_insuficiente(top1: Dict[str, Any], top2: Optional[Dict[str, Any]], top3: Optional[Dict[str, Any]]) -> bool:
    if not top1:
        return True
    conteudo = str(top1.get("conteudo") or "").strip()
    if len(conteudo) < 40:
        return True
    return False


def _termos_encontrados_no_texto(item: Dict[str, Any], termos: List[str]) -> List[str]:
    conteudo = _normalizar_texto(str(item.get("conteudo") or ""))
    metadados = item.get("metadados") or {}
    if isinstance(metadados, str):
        try:
            metadados = json.loads(metadados)
        except json.JSONDecodeError:
            metadados = {"valor_bruto": metadados}
    nome_arquivo = _normalizar_texto(str(metadados.get("nome_arquivo") or ""))
    texto = " ".join([conteudo, nome_arquivo])
    encontrados = [termo for termo in termos if termo in texto]
    return encontrados


def _montar_resposta_sem_base(pergunta: str) -> str:
    titulo = _gerar_titulo_tecnico(pergunta, {})
    return (
        f"{titulo}\n\n"
        "1. Resposta técnica\n"
        "A base atualmente indexada não contém evidência documental suficiente para responder com segurança técnica.\n\n"
        "2. Fundamentação encontrada na base\n"
        "Não foram encontrados trechos suficientemente aderentes ao tema para sustentar conclusão.\n\n"
        "3. Análise técnica\n"
        "Sem base documental adequada, a resposta deve permanecer em nível de cautela técnica e não deve ser convertida em orientação conclusiva.\n\n"
        "4. Providências recomendadas\n"
        "- Buscar documentos oficiais mais aderentes ao tema.\n"
        "- Revalidar a consulta com termos técnicos mais específicos.\n"
        "- Repetir a busca apenas quando houver base documental suficiente para sustentar a conclusão.\n\n"
        "5. Riscos de inconsistência\n"
        "Há risco de conclusão indevida, orientação imprecisa e fragilidade de auditoria se a pergunta for respondida sem base suficiente.\n\n"
        "6. Fontes consultadas\n"
        "- Fonte: n/d\n"
        "  Tipo de fonte: n/d\n"
        "  Nível de autoridade: n/d\n"
        "  Observação técnica: n/d"
    )


def _extrair_referencia_do_item(item: Dict[str, Any]) -> Dict[str, Any]:
    referencia = _construir_referencia_tecnica(item, item.get("metadados") or {})
    return referencia


def _construir_referencia_tecnica(item: Dict[str, Any], metadados: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(metadados, str):
        try:
            metadados = json.loads(metadados)
        except json.JSONDecodeError:
            metadados = {}

    conteudo = str(item.get("conteudo") or "")
    texto_completo = _normalizar_texto(" ".join([conteudo, json.dumps(metadados, ensure_ascii=False)]))
    nome_arquivo = str(metadados.get("nome_arquivo") or item.get("nome") or "").strip()
    caminho_storage = str(metadados.get("caminho_storage") or item.get("caminho_storage") or "").strip()

    # Nota técnica / orientação operacional
    if _eh_nota_tecnica_condicionalidade_v(texto_completo):
        item_6 = _capturar_regex(conteudo, [r"\b6\.4\b", r"\b6\.\d+\b"])
        item_7 = _capturar_regex(conteudo, [r"\b7\.1\b", r"\b7\.\d+\b"])
        secao = None
        titulo_secao = None
        if "processo de análise de informações e documentos" in texto_completo:
            secao = "item 7"
            titulo_secao = "Processo de Análise de Informações e Documentos"
        elif "aferição da condicionalidade v do vaar" in texto_completo:
            secao = "item 1"
            titulo_secao = "Proposta metodológica para a aferição da Condicionalidade V do VAAR"
        elif item_6 or item_7:
            secao = " e ".join([valor for valor in [item_6, item_7] if valor]) or None
        referencia_formatada = "Nota Técnica Conjunta nº 14/2025 INEP/MEC"
        if secao and titulo_secao:
            referencia_formatada = f"{referencia_formatada}, {secao}, {titulo_secao}"
        elif secao:
            referencia_formatada = f"{referencia_formatada}, {secao}"
        return {
            "nome_real_fonte": "Nota Técnica Conjunta nº 14/2025 INEP/MEC",
            "tipo_documento": "Nota técnica",
            "orgao": "INEP/MEC",
            "numero_norma": "14/2025",
            "ano_norma": 2025,
            "artigo": None,
            "paragrafo": None,
            "inciso": None,
            "item": secao,
            "secao": secao,
            "titulo_secao": titulo_secao,
            "referencia_tecnica_formatada": referencia_formatada,
            "data_publicacao": _extrair_data_publicacao_texto(conteudo),
            "ano_referencia": _extrair_ano_referencia_texto(conteudo) or 2025,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "etapa_do_ciclo": _inferir_etapa_do_ciclo(texto_completo, "nota_tecnica"),
            "observacao_tecnica": "Detalha procedimento operacional de comprovação da Condicionalidade V do VAAR.",
        }

    # Base normativa principal
    if (
        "lei nº 14.113" in texto_completo
        or "lei no 14 113" in texto_completo
        or "lei 14 113" in texto_completo
        or "dupla matricula" in texto_completo
        or "atendimento educacional especializado" in texto_completo
    ):
        artigo = _capturar_regex(conteudo, [r"art\.?\s*\d+[ºo]?", r"artigo\s*\d+[ºo]?"])
        paragrafo = _capturar_regex(conteudo, [r"§\s*\d+º?", r"parágrafo\s*único"])
        inciso = _capturar_regex(conteudo, [r"inciso\s+[ivxlcdm]+", r"inciso\s+[0-9]+"])
        secao = None
        if "dupla matrícula" in texto_completo or "atendimento educacional especializado" in texto_completo:
            secao = "disposição sobre dupla matrícula no AEE"
        referencia_formatada = "Lei nº 14.113/2020"
        detalhes = []
        if artigo:
            detalhes.append(artigo)
        if paragrafo:
            detalhes.append(paragrafo)
        if inciso:
            detalhes.append(inciso)
        if secao and not detalhes:
            detalhes.append(secao)
        if detalhes:
            referencia_formatada = f"{referencia_formatada}, " + ", ".join(detalhes)
        return {
            "nome_real_fonte": "Lei nº 14.113/2020",
            "tipo_documento": "Lei",
            "orgao": "Presidência da República",
            "numero_norma": "Lei nº 14.113/2020",
            "ano_norma": 2020,
            "artigo": artigo,
            "paragrafo": paragrafo,
            "inciso": inciso,
            "item": None,
            "secao": None,
            "titulo_secao": None,
            "referencia_tecnica_formatada": referencia_formatada,
            "data_publicacao": _extrair_data_publicacao_texto(conteudo),
            "ano_referencia": _extrair_ano_referencia_texto(conteudo) or 2020,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "etapa_do_ciclo": _inferir_etapa_do_ciclo(texto_completo, "lei"),
            "observacao_tecnica": "Fundamento legal da dupla matrícula e regras estruturantes do Fundeb.",
        }

    # Orientação oficial do MEC sobre Fundeb
    if "como funciona o fundeb" in texto_completo or "fundos estaduais" in texto_completo or "fundeb" in texto_completo and "ministerio da educacao" in texto_completo:
        secao = "Fundos Estaduais"
        referencia_formatada = "Orientação oficial do MEC sobre Fundos Estaduais do Fundeb, seção Fundos Estaduais"
        return {
            "nome_real_fonte": "Orientação oficial do MEC sobre Fundos Estaduais do Fundeb",
            "tipo_documento": "Orientação oficial",
            "orgao": "MEC",
            "numero_norma": None,
            "ano_norma": None,
            "artigo": None,
            "paragrafo": None,
            "inciso": None,
            "item": None,
            "secao": secao,
            "titulo_secao": secao,
            "referencia_tecnica_formatada": referencia_formatada,
            "data_publicacao": _extrair_data_publicacao_texto(conteudo),
            "ano_referencia": _extrair_ano_referencia_texto(conteudo),
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "etapa_do_ciclo": _inferir_etapa_do_ciclo(texto_completo, "orientacao_oficial"),
            "observacao_tecnica": "Explica a estrutura dos fundos estaduais do Fundeb e seu funcionamento.",
        }

    # Fallback seguro
    if nome_arquivo:
        if "condicionalidade v" in texto_completo or "vaar" in texto_completo:
            return {
                "nome_real_fonte": "Nota Técnica Conjunta nº 14/2025 INEP/MEC",
                "tipo_documento": "Nota técnica",
                "orgao": "INEP/MEC",
                "numero_norma": "14/2025",
                "ano_norma": 2025,
                "artigo": None,
                "paragrafo": None,
                "inciso": None,
                "item": None,
                "secao": None,
                "titulo_secao": None,
                "referencia_tecnica_formatada": "Nota Técnica Conjunta nº 14/2025 INEP/MEC",
                "data_publicacao": _extrair_data_publicacao_texto(conteudo),
                "ano_referencia": _extrair_ano_referencia_texto(conteudo) or 2025,
                "vigencia_inicio": None,
                "vigencia_fim": None,
                "etapa_do_ciclo": _inferir_etapa_do_ciclo(texto_completo, "nota_tecnica"),
                "observacao_tecnica": "Detalha procedimento operacional de comprovação da Condicionalidade V do VAAR.",
            }
        if "aee" in texto_completo or "dupla matricula" in texto_completo:
            return {
                "nome_real_fonte": "Lei nº 14.113/2020",
                "tipo_documento": "Lei",
                "orgao": "Presidência da República",
                "numero_norma": "Lei nº 14.113/2020",
                "ano_norma": 2020,
                "artigo": None,
                "paragrafo": None,
                "inciso": None,
                "item": None,
                "secao": "disposição sobre dupla matrícula no AEE",
                "titulo_secao": None,
                "referencia_tecnica_formatada": "Lei nº 14.113/2020, disposição sobre dupla matrícula no AEE",
                "data_publicacao": _extrair_data_publicacao_texto(conteudo),
                "ano_referencia": _extrair_ano_referencia_texto(conteudo) or 2020,
                "vigencia_inicio": None,
                "vigencia_fim": None,
                "etapa_do_ciclo": _inferir_etapa_do_ciclo(texto_completo, "lei"),
                "observacao_tecnica": "Fundamento legal da dupla matrícula e regras estruturantes do Fundeb.",
            }
        return {
            "nome_real_fonte": nome_arquivo,
            "tipo_documento": item.get("tipo_fonte") or "Documento",
            "orgao": None,
            "numero_norma": None,
            "ano_norma": None,
            "artigo": None,
            "paragrafo": None,
            "inciso": None,
            "item": None,
            "secao": None,
            "titulo_secao": None,
            "referencia_tecnica_formatada": nome_arquivo,
            "data_publicacao": _extrair_data_publicacao_texto(conteudo),
            "ano_referencia": _extrair_ano_referencia_texto(conteudo),
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "etapa_do_ciclo": _inferir_etapa_do_ciclo(texto_completo, item.get("tipo_fonte") or "documento"),
            "observacao_tecnica": "Referência técnica extraída apenas pelo título disponível na base.",
        }

    return {
        "nome_real_fonte": "Fonte não identificada",
        "tipo_documento": item.get("tipo_fonte") or "Documento",
        "orgao": None,
        "numero_norma": None,
        "ano_norma": None,
        "artigo": None,
        "paragrafo": None,
        "inciso": None,
        "item": None,
        "secao": None,
        "titulo_secao": None,
        "referencia_tecnica_formatada": "Fonte não identificada",
        "data_publicacao": None,
        "ano_referencia": None,
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "etapa_do_ciclo": None,
        "observacao_tecnica": "Não foi possível identificar a referência técnica com segurança.",
    }


def _extrair_metadados_temporais(item: Dict[str, Any]) -> Dict[str, Any]:
    metadados = item.get("metadados") or {}
    if isinstance(metadados, str):
        try:
            metadados = json.loads(metadados)
        except json.JSONDecodeError:
            metadados = {}

    referencia = _construir_referencia_tecnica(item, metadados)
    data_publicacao = referencia.get("data_publicacao") or _extrair_data_publicacao_texto(
        str(item.get("conteudo") or "") + " " + json.dumps(metadados, ensure_ascii=False)
    )
    serie_temporal_key = _montar_chave_serie_temporal(referencia, metadados)
    return {
        "data_publicacao": data_publicacao,
        "ano_referencia": referencia.get("ano_referencia") or _extrair_ano_referencia_texto(
            str(item.get("conteudo") or "") + " " + json.dumps(metadados, ensure_ascii=False)
        ),
        "vigencia_inicio": referencia.get("vigencia_inicio") or metadados.get("vigencia_inicio"),
        "vigencia_fim": referencia.get("vigencia_fim") or metadados.get("vigencia_fim"),
        "etapa_do_ciclo": referencia.get("etapa_do_ciclo") or metadados.get("etapa_do_ciclo"),
        "serie_temporal_key": serie_temporal_key,
        "versao_temporal": None,
    }


def _eh_intencao_temporal(pergunta_normalizada: str) -> bool:
    termos = (
        "valor",
        "previsao",
        "previsão",
        "aumento",
        "redução",
        "reducao",
        "atualizacao",
        "atualização",
        "mudanca",
        "mudança",
        "evolucao",
        "evolução",
        "comparacao",
        "comparação",
        "diferenca",
        "diferença",
        "anterior",
        "mais recente",
        "versao",
        "versão",
    )
    return any(termo in pergunta_normalizada for termo in termos)


def _inferir_tema_temporal(texto_normalizado: str, referencia: Dict[str, Any], metadados: Dict[str, Any]) -> str:
    if any(termo in texto_normalizado for termo in ("condicionalidade v", "simec", "bncc", "referencial curricular", "ato de aprovacao", "upload")):
        return "vaar_condicionalidade_v"
    if any(termo in texto_normalizado for termo in ("vaaf", "vaf", "valor anual por aluno")):
        return "vaaf"
    if any(termo in texto_normalizado for termo in ("vaat", "valor anual total por aluno")):
        return "vaat"
    if any(termo in texto_normalizado for termo in ("aee", "dupla matricula", "dupla matrícula")):
        return "aee_dupla_matricula"
    if any(termo in texto_normalizado for termo in ("matricula ponderada", "matrículas ponderadas", "matriculas ponderadas")):
        return "matriculas_ponderadas"
    if any(termo in texto_normalizado for termo in ("coeficiente", "complementacao da uniao", "complementação da união", "previsao", "previsão", "estimativa", "atualizacao", "atualização", "retificacao", "retificação")):
        return "fundeb_orcamentario"
    if "fundeb" in texto_normalizado:
        nome_real = str(referencia.get("nome_real_fonte") or metadados.get("nome_arquivo") or "fonte_sem_nome")
        partes = [
            token
            for token in _normalizar_texto(nome_real).split()
            if len(token) >= 4 and token not in {"documento", "fonte", "arquivo", "fundeb"}
        ]
        if partes:
            return "fundeb_" + "_".join(partes[:4])
        return "fundeb_geral"

    nome_real = str(referencia.get("nome_real_fonte") or metadados.get("nome_arquivo") or "fonte_sem_nome")
    partes = [
        token
        for token in _normalizar_texto(nome_real).split()
        if len(token) >= 4 and token not in {"documento", "fonte", "arquivo"}
    ]
    if partes:
        return "_".join(partes[:5])
    return "serie_indefinida"


def _marcar_versoes_temporais(resultados: List[Dict[str, Any]], intencao_temporal: bool) -> List[Dict[str, Any]]:
    grupos: Dict[str, List[Dict[str, Any]]] = {}
    for item in resultados:
        chave = item.get("serie_temporal_key") or item.get("nome_real_fonte") or item.get("tipo_documento") or "serie_indefinida"
        grupos.setdefault(chave, []).append(item)

    for grupo in grupos.values():
        grupo.sort(key=_chave_temporal_ordenacao, reverse=True)
        if len(grupo) == 1:
            grupo[0]["versao_temporal"] = "versão única"
            continue
        for indice, item in enumerate(grupo):
            if indice == 0:
                item["versao_temporal"] = "versão mais recente"
            elif indice == len(grupo) - 1:
                item["versao_temporal"] = "versão anterior"
            else:
                item["versao_temporal"] = "versão intermediária"

    if not intencao_temporal:
        return resultados

    return resultados


def _montar_chave_serie_temporal(referencia: Dict[str, Any], metadados: Dict[str, Any]) -> str:
    texto_base = " ".join(
        [
            str(referencia.get("nome_real_fonte") or ""),
            str(referencia.get("tipo_documento") or ""),
            str(referencia.get("orgao") or ""),
            str(referencia.get("titulo_secao") or ""),
            str(referencia.get("secao") or ""),
            str(metadados.get("nome_arquivo") or ""),
        ]
    )
    tema = _inferir_tema_temporal(_normalizar_texto(texto_base), referencia, metadados)
    orgao = _normalizar_texto(str(referencia.get("orgao") or metadados.get("orgao") or ""))
    tipo = _normalizar_texto(str(referencia.get("tipo_documento") or ""))
    return _normalizar_texto(" ".join(part for part in [tema, orgao, tipo] if part))


def _chave_temporal_ordenacao(item: Dict[str, Any]) -> tuple:
    data = item.get("data_publicacao")
    ano = item.get("ano_norma") or item.get("ano_referencia") or 0
    data_ord = _parse_data_para_ordenacao(data)
    return (data_ord or 0, int(ano) if str(ano).isdigit() else 0, float(item.get("similarity") or 0.0))


def _parse_data_para_ordenacao(valor: Any) -> Optional[int]:
    if not valor:
        return None
    texto = str(valor).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        return int(f"{m.group(1)}{m.group(2)}{m.group(3)}")
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if m:
        return int(f"{m.group(3)}{m.group(2)}{m.group(1)}")
    m = re.search(r"(\d{4})", texto)
    if m:
        return int(f"{m.group(1)}0101")
    return None


def _formatar_vigencia(inicio: Any, fim: Any) -> str:
    if not inicio and not fim:
        return "n/d"
    if inicio and fim:
        return f"{inicio} até {fim}"
    if inicio:
        return f"a partir de {inicio}"
    return f"até {fim}"


def _montar_comparativo_temporal(pergunta: str, resultados: List[Dict[str, Any]]) -> str:
    if not _eh_intencao_temporal(_normalizar_texto(pergunta)):
        return ""

    grupos: Dict[str, List[Dict[str, Any]]] = {}
    for item in resultados:
        chave = item.get("serie_temporal_key") or item.get("nome_real_fonte") or item.get("tipo_documento") or "serie_indefinida"
        grupos.setdefault(chave, []).append(item)

    melhor_grupo: Optional[List[Dict[str, Any]]] = None
    melhor_pontuacao: tuple = (0, 0, 0)
    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        ordenado = sorted(grupo, key=_chave_temporal_ordenacao, reverse=True)
        candidato = (
            len(ordenado),
            _parse_data_para_ordenacao(ordenado[0].get("data_publicacao")) or 0,
            float(ordenado[0].get("final_score") or 0.0),
        )
        if candidato > melhor_pontuacao:
            melhor_pontuacao = candidato
            melhor_grupo = ordenado

    if not melhor_grupo:
        return ""

    atual = melhor_grupo[0]
    anterior = melhor_grupo[1]

    valor_atual, unidade_atual, contexto_atual = _extrair_valor_relevante(atual, pergunta)
    valor_anterior, unidade_anterior, contexto_anterior = _extrair_valor_relevante(anterior, pergunta)

    linhas = ["7. Série temporal normativa/orçamentária"]
    linhas.append(
        f"- Publicação anterior: {anterior.get('referencia_tecnica_formatada') or anterior.get('nome_real_fonte') or 'Fonte não identificada'} "
        f"({anterior.get('data_publicacao') or 'data não identificada'})"
    )
    linhas.append(
        f"- Publicação mais recente: {atual.get('referencia_tecnica_formatada') or atual.get('nome_real_fonte') or 'Fonte não identificada'} "
        f"({atual.get('data_publicacao') or 'data não identificada'})"
    )

    if valor_atual is not None and valor_anterior is not None and unidade_atual == unidade_anterior:
        diferenca_absoluta = valor_atual - valor_anterior
        variacao_percentual = ((diferenca_absoluta / valor_anterior) * 100) if valor_anterior not in (0, 0.0) else None
        linhas.append(
            f"- Valor anterior: {valor_anterior:g}{unidade_anterior}"
        )
        linhas.append(
            f"- Valor atualizado: {valor_atual:g}{unidade_atual}"
        )
        linhas.append(
            f"- Diferença absoluta: {diferenca_absoluta:g}{unidade_atual}"
        )
        if variacao_percentual is not None:
            linhas.append(
                f"- Variação percentual: {variacao_percentual:.2f}%"
            )
        linhas.append(
            "- Interpretação técnica: a versão mais recente deve ser usada para a situação atual, e a versão anterior deve ser preservada como histórico de comparação."
        )
    else:
        linhas.append(
            "- Comparação numérica: a base consultada mostrou evolução documental, mas não trouxe valores comparáveis com segurança suficiente no trecho recuperado."
        )
        linhas.append(
            "- Interpretação técnica: a versão mais recente prevalece para a situação atual, enquanto a anterior deve ser mantida como histórico técnico."
        )

    if contexto_atual or contexto_anterior:
        linhas.append(
            f"- Contexto observado: {contexto_anterior or 'n/d'} -> {contexto_atual or 'n/d'}"
        )

    return "\n".join(linhas)


def _extrair_valor_relevante(item: Dict[str, Any], pergunta: str) -> tuple[Optional[float], str, Optional[str]]:
    conteudo = str(item.get("conteudo") or "")
    texto = _normalizar_texto(conteudo)
    pergunta_n = _normalizar_texto(pergunta)
    unidade = ""
    contexto = None

    for termo in ["vaaf", "vaat", "vaar", "valor", "coeficiente", "estimativa", "complementacao", "complementação"]:
        idx = texto.find(termo)
        if idx != -1:
            contexto = conteudo[max(0, idx - 80): idx + 220].strip()
            break

    if "r$" in conteudo.lower():
        unidade = " R$"

    padroes = [
        r"R\$\s*[\d\.\s]+,\d+",
        r"\b\d{1,3}(?:\.\d{3})*(?:,\d+)?\b",
        r"\b\d+,\d+\b",
        r"\b\d+\b",
    ]
    for padrao in padroes:
        match = re.search(padrao, conteudo)
        if match:
            bruto = match.group(0).replace("R$", "").strip()
            bruto = bruto.replace(".", "").replace(" ", "").replace(",", ".")
            try:
                valor = float(bruto)
            except ValueError:
                continue
            if "r$" in match.group(0).lower():
                unidade = " R$"
            elif any(token in pergunta_n for token in ("percentual", "percentuais", "variação", "variacao", "%")):
                unidade = " %"
            return valor, unidade, contexto

    return None, unidade, contexto


def _eh_nota_tecnica_condicionalidade_v(texto_completo: str) -> bool:
    termos_obrigatorios = (
        "nota tecnica conjunta",
        "inep",
        "mec",
        "condicionalidade v",
    )
    if not all(termo in texto_completo for termo in termos_obrigatorios):
        return False
    return any(
        termo in texto_completo
        for termo in (
            "simec",
            "upload",
            "bncc",
            "referencial curricular",
            "ato de aprovacao",
            "ato de aprovação",
            "proposta metodologica para a afericao da condicionalidade v do vaar",
            "processo de analise de informacoes e documentos",
        )
    )


def _extrair_ano_referencia_texto(texto: str) -> Optional[int]:
    if not texto:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", texto)
    if match:
        return int(match.group(0))
    return None


def _extrair_data_publicacao_texto(texto: str) -> Optional[str]:
    if not texto:
        return None
    texto_normalizado = _normalizar_texto(texto)
    match = re.search(r"\b(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})\b", texto_normalizado)
    if match:
        mes = _mapear_mes_pt(match.group(2))
        if mes:
            return f"{match.group(3)}-{mes:02d}-{int(match.group(1)):02d}"
    match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", texto)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def _inferir_etapa_do_ciclo(texto_normalizado: str, tipo_documento: str) -> Optional[str]:
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
    if tipo_documento == "nota_tecnica":
        return "nota técnica"
    if tipo_documento == "lei":
        return "publicação legal"
    return None


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


def _capturar_regex(texto: str, padroes: List[str]) -> Optional[str]:
    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)
        if match:
            valor = match.group(0).strip()
            valor = valor.replace("§ ", "§ ").replace("  ", " ")
            return valor
    return None


def consultar_dados(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    tabelas = [
        "dados_municipios",
        "dados_ponderacoes",
        "dados_receitas_fundeb",
        "dados_matriculas",
    ]

    consulta = str(query.get("consulta") or "").strip().lower()
    municipio = str(query.get("municipio") or "").strip().lower()
    ano_referencia = query.get("ano_referencia")
    limite = int(query.get("limite") or 20)

    if limite < 1:
        raise ValueError("limite precisa ser maior ou igual a 1.")

    resultados: List[Dict[str, Any]] = []

    for tabela in tabelas:
        try:
            resposta = client.table(tabela).select("*").limit(limite).execute()
        except Exception as exc:  # pragma: no cover - depende do Supabase
            logger.warning("Falha ao consultar tabela '%s': %s", tabela, exc)
            continue

        for linha in resposta.data or []:
            if _linha_corresponde(linha, consulta, municipio, ano_referencia):
                resultados.append({"tabela": tabela, **linha})
                if len(resultados) >= limite:
                    return resultados

    return resultados


def _linha_corresponde(linha: Dict[str, Any], consulta: str, municipio: str, ano_referencia: Any) -> bool:
    texto_linha = json.dumps(linha, ensure_ascii=False).lower()

    if consulta and consulta not in texto_linha:
        return False

    if municipio and municipio not in texto_linha:
        return False

    if ano_referencia is not None:
        ano_texto = str(ano_referencia)
        if ano_texto not in texto_linha:
            return False

    return True
