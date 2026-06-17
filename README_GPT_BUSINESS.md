# GPT Business - Auditor Censo Escolar Fundeb

Este guia explica como usar a API com um GPT chamado `Auditor Censo Escolar Fundeb`.

## 1. Como criar o GPT

1. Abra o criador de GPTs no ChatGPT Business.
2. Crie um GPT novo com o nome `Auditor Censo Escolar Fundeb`.
3. Cole as instrucoes abaixo no campo de comportamento.
4. Adicione a Action usando o arquivo `gpt_action/openapi.yaml`.
5. Configure o header `x-api-key`.
6. Salve e teste primeiro o endpoint `/health`.

## 2. Instrucoes do agente

Copie este bloco para o GPT:

```text
Voce e o Auditor Censo Escolar Fundeb.

Voce deve atuar como consultor especialista em Censo Escolar, Fundeb, AEE e educacao especial.

Regras:
- priorize fontes oficiais;
- diferencie lei, orientacao oficial, estudo academico e material informativo;
- nunca trate artigo como lei;
- nunca invente fundamento;
- consulte a API quando precisar de base tecnica;
- indique fonte, pagina, tipo de fonte e nivel de autoridade;
- declare insuficiencia quando a base nao permitir conclusao segura;
- ajude gestores municipais com checklists, cronogramas, tabelas de conferencia e orientacoes praticas.
```

## 3. Como adicionar a Action

1. No GPT, abra a area de Actions.
2. Importe o arquivo `gpt_action/openapi.yaml`.
3. Confirme o servidor `https://api.saberes.cloud`.
4. Marque o header `x-api-key` como autentificacao.

## 4. Como configurar a chave

Use a mesma chave definida no `.env` da API.

Nao compartilhe a chave em conversa publica.

## 5. Como testar o `/buscar-conhecimento`

Depois que a base estiver populada, o GPT pode chamar:

- `POST /buscar-conhecimento`

Exemplo de entrada:

```json
{
  "pergunta": "Qual a regra de atendimento educacional especializado?",
  "limite": 8
}
```

## 6. Observacao importante

Nesta entrega inicial, a API ainda nao processa PDFs de verdade. A estrutura ja ficou pronta para a proxima etapa.
