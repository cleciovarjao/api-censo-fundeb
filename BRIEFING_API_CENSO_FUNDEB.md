# BRIEFING_API_CENSO_FUNDEB

## 1. Orientação ao Codex

Você será meu desenvolvedor técnico no projeto `API-CENSO-FUNDEB`.

Eu sou iniciante e não sei programar. Trabalhe sempre com instruções simples, comandos prontos para copiar e colar, e sem executar ações destrutivas sem minha autorização.

Antes de rodar qualquer comando que altere servidor, banco, arquivos ou configurações, explique o que será feito e aguarde confirmação.

Não processe todos os PDFs automaticamente. Primeiro crie a estrutura do projeto e aguarde minha autorização para testar apenas 1 PDF.

Nunca coloque chaves reais no código. Nunca peça para eu colar chaves secretas em conversa pública. As chaves reais serão colocadas manualmente no arquivo `.env`.

---

## 2. Projeto

Nome da pasta/projeto:

`API-CENSO-FUNDEB`

Agente final:

`Auditor Censo Escolar Fundeb`

---

## 3. Ferramentas disponíveis

- Supabase
- GPT OpenAI Business
- Codex rodando na minha máquina
- VPS KVM 2 da Hostinger
- domínio `saberes.cloud`
- subdomínio desejado: `api.saberes.cloud`

Arquitetura desejada:

```text
GPT OpenAI Business
→ Action do GPT
→ https://api.saberes.cloud
→ API hospedada na VPS Hostinger
→ Supabase
→ documentos, dados, vetores e tabelas
```

---

## 4. Supabase já configurado

Buckets:

- `fundeb-conhecimento`
- `fundeb-dados`
- `fundeb-aprimorada`

Organização do bucket `fundeb-conhecimento`:

- `01_normas_oficiais`
- `02_orientacoes_oficiais`
- `03_estudos_academicos`
- `04_materiais_informativos`
- `05_perguntas_respostas`

Tabelas já criadas:

- `fontes_fundeb`
- `conhecimento_trechos`
- `arquivos_dados`
- `dados_municipios`
- `dados_ponderacoes`
- `dados_receitas_fundeb`
- `dados_matriculas`
- `base_aprimorada`

---

## 5. Objetivo técnico

Criar uma API em Python/FastAPI capaz de:

1. Processar PDFs do bucket `fundeb-conhecimento`.
2. Extrair texto dos PDFs.
3. Dividir o texto em trechos com sobreposição.
4. Gerar embeddings com OpenAI usando `text-embedding-3-small`.
5. Salvar embeddings na tabela `conhecimento_trechos`.
6. Registrar documentos na tabela `fontes_fundeb`.
7. Criar endpoint para busca vetorial.
8. Criar endpoint para processamento de PDFs.
9. Criar estrutura inicial para consulta de dados.
10. Criar arquivo OpenAPI para conectar ao GPT Business.
11. Criar arquivos de deploy para VPS Hostinger.
12. Criar documentação didática.

---

## 6. Estrutura de arquivos

Crie:

```text
API-CENSO-FUNDEB/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── supabase_client.py
│   ├── embeddings.py
│   ├── pdf_processor.py
│   ├── search_service.py
│   ├── security.py
│   └── models.py
├── scripts/
│   ├── processar_pdfs_fundeb.py
│   └── testar_um_pdf.py
├── deployment/
│   ├── setup_vps_ubuntu.sh
│   ├── agente-fundeb.service
│   ├── nginx_api_saberes_cloud.conf
│   └── certbot_ssl_instrucoes.md
├── gpt_action/
│   └── openapi.yaml
├── .env.example
├── requirements.txt
├── README.md
└── README_GPT_BUSINESS.md
```

---

## 7. Variáveis de ambiente

Crie `.env.example` com:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
API_SECRET_KEY=
```

As chaves reais serão preenchidas manualmente no `.env`.

---

## 8. Requisitos técnicos

Use:

- Python
- FastAPI
- Uvicorn
- Supabase Python Client
- OpenAI Python SDK
- PyMuPDF
- python-dotenv
- pydantic
- requests, se necessário

Modelo de embedding:

`text-embedding-3-small`

Dimensão vetorial:

compatível com `vector(1536)`.

---

## 9. Endpoints obrigatórios

### GET `/health`

Retorno:

```json
{
  "status": "ok",
  "service": "auditor-censo-escolar-fundeb"
}
```

### POST `/buscar-conhecimento`

Exigir header:

`x-api-key`

Recebe:

```json
{
  "pergunta": "texto da pergunta",
  "limite": 8
}
```

Funcionamento:

- gerar embedding da pergunta;
- consultar `conhecimento_trechos`;
- retornar trechos mais relevantes;
- priorizar menor `nivel_autoridade`;
- retornar `conteudo`, `pagina`, `nome` da fonte, `caminho_storage`, `tipo_fonte`, `nivel_autoridade`, `similarity` e `metadados`.

### POST `/processar-pdfs`

Exigir header:

`x-api-key`

Recebe:

```json
{
  "limit": 1
}
```

Funcionamento:

- listar PDFs do bucket `fundeb-conhecimento`;
- verificar quais ainda não existem em `fontes_fundeb` pelo campo `caminho_storage`;
- processar apenas os novos;
- permitir `limit` para testar apenas 1 PDF;
- extrair texto por página usando PyMuPDF;
- se página não tiver texto, registrar aviso de possível OCR;
- dividir texto em trechos de 1500 a 2500 caracteres;
- usar sobreposição de 300 caracteres;
- gerar embeddings;
- salvar em `conhecimento_trechos`;
- salvar fonte em `fontes_fundeb`.

### POST `/consultar-dados`

Exigir header:

`x-api-key`

Criar estrutura inicial para futuras consultas às tabelas:

- `dados_municipios`
- `dados_ponderacoes`
- `dados_receitas_fundeb`
- `dados_matriculas`

---

## 10. Classificação por pasta

Se caminho contiver `01_normas_oficiais`:

```text
categoria = conhecimento
subcategoria = normas_oficiais
tipo_fonte = norma_oficial
nivel_autoridade = 1
```

Se caminho contiver `02_orientacoes_oficiais`:

```text
categoria = conhecimento
subcategoria = orientacoes_oficiais
tipo_fonte = orientacao_oficial
nivel_autoridade = 2
```

Se caminho contiver `03_estudos_academicos`:

```text
categoria = conhecimento
subcategoria = estudos_academicos
tipo_fonte = estudo_academico
nivel_autoridade = 4
```

Se caminho contiver `04_materiais_informativos`:

```text
categoria = conhecimento
subcategoria = materiais_informativos
tipo_fonte = material_informativo
nivel_autoridade = 5
```

Se caminho contiver `05_perguntas_respostas`:

```text
categoria = conhecimento
subcategoria = perguntas_respostas
tipo_fonte = perguntas_respostas
nivel_autoridade = 5
```

---

## 11. Campos das tabelas

### `fontes_fundeb`

Inserir:

- `nome`
- `categoria`
- `subcategoria`
- `tipo_arquivo`
- `bucket`
- `caminho_storage`
- `origem`
- `orgao`
- `ano_referencia`
- `status`
- `nivel_autoridade`
- `observacoes`

Quando não souber origem, órgão ou ano, usar `null`.

Status deve ser `ativo`.

### `conhecimento_trechos`

Inserir:

- `fonte_id`
- `conteudo`
- `pagina`
- `ordem_trecho`
- `tema`
- `tipo_fonte`
- `nivel_autoridade`
- `ano_referencia`
- `embedding`
- `metadados`

`metadados` deve conter:

- `bucket`
- `caminho_storage`
- `nome_arquivo`
- `subcategoria`
- `tipo_fonte`
- `nivel_autoridade`
- `pagina`
- `ordem_trecho`

---

## 12. Busca vetorial

No `README.md`, inclua uma função SQL recomendada para Supabase chamada:

`match_conhecimento_trechos`

Ela deve receber:

- `query_embedding vector(1536)`
- `match_count int`

E retornar:

- `id`
- `fonte_id`
- `conteudo`
- `pagina`
- `tipo_fonte`
- `nivel_autoridade`
- `metadados`
- `similarity`

---

## 13. Deploy na VPS Hostinger

Criar arquivos para Ubuntu.

### `deployment/setup_vps_ubuntu.sh`

Deve:

1. atualizar pacotes;
2. instalar python3, pip, venv, git, nginx;
3. criar pasta `/opt/agente-fundeb`;
4. orientar como copiar o projeto;
5. criar ambiente virtual;
6. instalar dependências;
7. orientar criação do `.env`;
8. configurar systemd;
9. configurar nginx.

### `deployment/agente-fundeb.service`

Rodar:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### `deployment/nginx_api_saberes_cloud.conf`

Configurar proxy:

```text
api.saberes.cloud → 127.0.0.1:8000
```

### SSL

Criar instruções com Certbot para:

`api.saberes.cloud`

### DNS

No README, explicar que preciso criar registro A no domínio `saberes.cloud`:

```text
Tipo: A
Nome: api
Valor: IP público da VPS
```

---

## 14. GPT Business

Criar `gpt_action/openapi.yaml` com:

- servidor `https://api.saberes.cloud`;
- `/health`;
- `/buscar-conhecimento`;
- `/processar-pdfs`;
- `/consultar-dados`;
- autenticação por `x-api-key`.

Criar `README_GPT_BUSINESS.md` explicando:

1. Como criar o GPT “Auditor Censo Escolar Fundeb”.
2. Como configurar as instruções do agente.
3. Como adicionar Action.
4. Como importar `openapi.yaml`.
5. Como configurar `x-api-key`.
6. Como testar `/buscar-conhecimento`.

---

## 15. Instruções do agente GPT

Inclua no `README_GPT_BUSINESS.md` um bloco de instruções para o GPT com estas regras:

O GPT é o **Auditor Censo Escolar Fundeb**.

Ele deve:

- atuar como consultor especialista em Censo Escolar, Fundeb, AEE e educação especial;
- priorizar fontes oficiais;
- diferenciar lei, orientação oficial, estudo acadêmico e material informativo;
- nunca tratar artigo como lei;
- nunca inventar fundamento;
- consultar a API quando precisar de base técnica;
- indicar fonte, página, tipo de fonte e nível de autoridade;
- declarar insuficiência quando a base não permitir conclusão segura;
- ajudar gestores municipais com checklists, cronogramas, tabelas de conferência e orientações práticas.

---

## 16. README principal

O `README.md` deve ser didático e conter:

1. O que é o projeto.
2. Como criar o `.env`.
3. Como instalar dependências.
4. Como testar com 1 PDF.
5. Como rodar a API local.
6. Como testar `/health`.
7. Como processar PDFs com `limit 1`.
8. Como verificar no Supabase.
9. Como subir para VPS.
10. Como configurar `api.saberes.cloud`.
11. Como configurar SSL.
12. Como conectar ao GPT Business.

Comandos esperados:

```bash
python -m venv .venv
```

No Windows:

```bash
.venv\Scripts\activate
```

No Linux:

```bash
source .venv/bin/activate
```

Instalar dependências:

```bash
pip install -r requirements.txt
```

Testar 1 PDF:

```bash
python scripts/processar_pdfs_fundeb.py --limit 1
```

Rodar API local:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Testar local:

```bash
curl http://127.0.0.1:8000/health
```

Testar produção:

```bash
curl https://api.saberes.cloud/health
```

---

## 17. Ordem obrigatória

Não processe todos os PDFs automaticamente.

Primeiro:

1. crie tudo;
2. explique o que foi criado;
3. aguarde minha autorização;
4. teste apenas 1 PDF;
5. só depois autorize processamento completo.
