# API Censo Fundeb

Esta pasta contem a base inicial da API `Auditor Censo Escolar Fundeb`.

O objetivo desta primeira etapa e deixar tudo pronto para:

- abrir a API localmente;
- testar o endpoint `GET /health`;
- conectar depois com Supabase e OpenAI;
- preparar o processamento de PDFs;
- preparar a publicacao na VPS Hostinger;
- preparar a integracao com GPT Business.

## Proxima etapa segura

Antes de qualquer processamento, a recomendacao e:

1. preencher o arquivo `.env` com as chaves reais no seu computador;
2. iniciar a API localmente;
3. testar apenas `GET /health`.

O processamento de PDFs deve continuar bloqueado ate voce autorizar o teste com apenas 1 PDF.

## 1. O que foi criado

- estrutura de pastas do projeto;
- API FastAPI com endpoints iniciais;
- arquivos de ambiente;
- scripts de apoio;
- arquivos de deploy;
- arquivo OpenAPI para o GPT Business.

## 2. Como criar o arquivo `.env`

Crie um arquivo chamado `.env` na raiz do projeto com este conteudo:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
API_SECRET_KEY=
```

As chaves reais nao devem ser colocadas em conversa. Preencha manualmente no seu computador.

## 3. Como instalar as dependencias

No Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

No Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Como testar com 1 PDF

Ainda nao vamos processar PDFs em lote. Quando voce autorizar a proxima etapa, o comando sera:

```bash
python scripts/processar_pdfs_fundeb.py --limit 1
```

## 5. Como rodar a API local

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 6. Como testar o endpoint de saude

```bash
curl http://127.0.0.1:8000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "service": "auditor-censo-escolar-fundeb"
}
```

## 7. Como processar PDFs com limite 1

Mais tarde, quando voce autorizar, use:

```bash
python scripts/processar_pdfs_fundeb.py --limit 1
```

## 8. Como verificar no Supabase

As tabelas que o projeto vai usar sao:

- `fontes_fundeb`
- `conhecimento_trechos`
- `arquivos_dados`
- `dados_municipios`
- `dados_ponderacoes`
- `dados_receitas_fundeb`
- `dados_matriculas`
- `base_aprimorada`

## 9. Como subir para a VPS

Arquivos de apoio:

- `deployment/setup_vps_ubuntu.sh`
- `deployment/agente-fundeb.service`
- `deployment/nginx_api_saberes_cloud.conf`
- `deployment/certbot_ssl_instrucoes.md`

## 10. Como configurar `api.saberes.cloud`

No DNS do dominio `saberes.cloud`, crie:

- Tipo: `A`
- Nome: `api`
- Valor: IP publico da VPS

## 11. Como configurar SSL

Depois de apontar o DNS, instale o Certbot e rode:

```bash
sudo certbot --nginx -d api.saberes.cloud
```

## 12. Como conectar ao GPT Business

Use o arquivo:

```text
gpt_action/openapi.yaml
```

Esse arquivo apresenta os endpoints que o GPT vai chamar.

## 13. SQL recomendado para busca vetorial

No Supabase, uma funcao util para busca e:

```sql
create or replace function match_conhecimento_trechos(
  query_embedding vector(1536),
  match_count int
)
returns table (
  id bigint,
  fonte_id bigint,
  conteudo text,
  pagina int,
  tipo_fonte text,
  nivel_autoridade int,
  metadados jsonb,
  similarity float
)
language sql
stable
as $$
  select
    ct.id,
    ct.fonte_id,
    ct.conteudo,
    ct.pagina,
    ct.tipo_fonte,
    ct.nivel_autoridade,
    ct.metadados,
    1 - (ct.embedding <=> query_embedding) as similarity
  from conhecimento_trechos ct
  order by ct.embedding <=> query_embedding
  limit match_count;
$$;
```
