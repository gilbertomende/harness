# AI Harness — Stage v0.2.0

Harness FastAPI independente de provedor com sessão PostgreSQL, agent loop, tool registry, Ollama/OpenRouter/9Router (camada OpenAI-compatible), RAG/pgvector, MCP, sandbox, JWT/RBAC, auditoria e fallback automático de modelos.

## Topologia recomendada

- **Local:** Docker Desktop/Compose (`docker-compose.yml`) para desenvolvimento e homologação.
- **Stage/produção:** VPS Ubuntu LTS + Docker Engine/Compose (`compose.stage.yaml`) + reverse proxy TLS. Mantenha PostgreSQL, harness e Ollama em rede privada e exponha somente o HTTPS do reverse proxy.
- **Vercel:** opcional para um frontend Next.js; não é o destino recomendado para o backend stateful deste harness.

| Arquivo | Uso |
|---|---|
| `docker-compose.yml` | desenvolvimento local; portas só em `127.0.0.1` |
| `compose.e2e.yaml` | overlay de homologação: stub OpenAI-compatible + servidor MCP demo (nunca em stage) |
| `compose.stage.yaml` | VPS; `restart: unless-stopped`, imagem sobrescrevível por `HARNESS_IMAGE` |

## Desenvolvimento local

Pré-requisitos: Docker com Compose v2 e Python 3.12 (apenas para os testes unitários).

### 1. Configuração (`.env` nunca vai para o Git)

```bash
cp .env.example .env
# gere valores aleatórios para os três segredos:
sed -i \
  -e "s/CHANGE_DB_PASSWORD/$(openssl rand -hex 24)/" \
  -e "s/CHANGE_TO_LONG_RANDOM_SECRET/$(openssl rand -hex 32)/" \
  -e "s/CHANGE_ADMIN_PASSWORD/$(openssl rand -hex 16)/" .env
```

- O Compose monta `DATABASE_URL` a partir de `POSTGRES_PASSWORD`. Use só `[A-Za-z0-9]` nessa senha.
- O app **recusa iniciar** se `JWT_SECRET` (mínimo de 32 caracteres) ou `ADMIN_PASSWORD` (mínimo de 12) ainda tiverem o valor de exemplo.
- Para ver a senha do admin: `grep ADMIN_PASSWORD .env`.

### 2. Testes unitários

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Os testes usam SQLite e um servidor MCP em memória, sem Docker nem rede.

### 3. Build e subida com Ollama real

```bash
docker compose build
docker compose --profile local-model up -d
docker compose ps                        # postgres e harness devem ficar "healthy"
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama pull nomic-embed-text
curl -s http://127.0.0.1:8000/health
```

### 4. Autenticação e chamadas

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"$(grep ^ADMIN_PASSWORD .env | cut -d= -f2)\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST http://127.0.0.1:8000/chat -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Olá"}'
curl -s -X POST http://127.0.0.1:8000/rag/ingest -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"source":"doc.md","text":"conteúdo"}'
curl -s --get http://127.0.0.1:8000/rag/search --data-urlencode "q=conteúdo" -H "Authorization: Bearer $TOKEN"
```

Reenvie o `session_id` retornado pelo `/chat` para continuar a mesma sessão.

### 5. Homologação

**Sem modelo real (determinística; é o mesmo fluxo do job `e2e` do CI).** Esse modo sobe um stub OpenAI-compatible e um servidor MCP (streamable HTTP) usando a própria imagem do harness. Ele valida:

- health e autenticação
- adapter OpenAI-compatible
- persistência de sessão, inclusive após restart
- tool calling e bloqueios do sandbox
- RAG com pgvector
- MCP e o fluxo de aprovação

```bash
docker compose build
docker compose -f docker-compose.yml -f compose.e2e.yaml up -d --no-build --wait
python3 e2e/smoke.py --restart          # esperado: "27/27 checks passed"
docker compose -f docker-compose.yml -f compose.e2e.yaml down
```

**Com modelos reais.** Com a stack do passo 3 no ar e os modelos já baixados:

```bash
python3 e2e/real_model_check.py                          # Ollama: chat, tool calling, embeddings/RAG, private
python3 e2e/real_model_check.py --provider openrouter    # requer OPENROUTER_API_KEY no .env
```

### 6. Inspeção e limpeza

```bash
docker compose logs -f harness
docker compose exec postgres psql -U harness -d harness -c "select extversion from pg_extension where extname='vector';"
docker compose exec postgres psql -U harness -d harness -c "select action, count(*) from audit_events group by 1;"
docker compose --profile local-model down        # mantém volumes
docker compose --profile local-model down -v     # apaga banco e modelos
```

### Proxy corporativo com inspeção TLS

Se o `pip install` do build falhar com `CERTIFICATE_VERIFY_FAILED`, passe a CA do proxy como secret de build. Ela não fica gravada na imagem.

```bash
docker build --secret id=pip_ca,src=/caminho/ca.crt -t ai-harness:local .
docker compose up -d --no-build
```

## Stage (VPS Ubuntu)

1. Crie o `.env` como no passo 1 do desenvolvimento local.
2. Suba a stack:
   - com build na própria VPS: `docker compose -f compose.stage.yaml --profile local-model up -d --build`
   - ou com a imagem publicada no GHCR: `HARNESS_IMAGE=ghcr.io/<owner>/harness:v0.2.0 docker compose -f compose.stage.yaml --profile local-model up -d`
3. Baixe os modelos:
   - `docker compose -f compose.stage.yaml exec ollama ollama pull qwen3:8b`
   - `docker compose -f compose.stage.yaml exec ollama ollama pull nomic-embed-text`
4. Verifique: `curl http://127.0.0.1:8000/health`. Depois publique via reverse proxy TLS; a porta 8000 fica só em `127.0.0.1`.

O container do PostgreSQL recebe apenas as credenciais do banco, sem JWT nem chaves de API.

## Model router

- `DEFAULT_PROVIDER=auto` tenta Ollama → 9Router → OpenRouter.
  - Provedores sem modelo configurado são pulados.
  - O OpenRouter também é pulado quando não há `OPENROUTER_API_KEY`.
- É possível fixar `provider` e `model` em cada request.
- `private=true` só aceita provider local (Ollama). Pedir `provider=openrouter` ou `9router` com `private=true` retorna 403.
- Cada provider usa timeout `LLM_TIMEOUT_SECONDS` (padrão 120) e `LLM_MAX_RETRIES` (padrão 1). O fallback entre providers é o mecanismo principal de nova tentativa.
- Quando nenhum provider responde, `/chat` retorna **503** com o motivo. Falhas do provider de embeddings em `/rag/*` também retornam 503; isso inclui modelo não baixado e dimensão diferente de 768.

## Aprovação de ferramentas mutáveis

Ferramentas MCP são tratadas como mutáveis, exceto as que o servidor declara `readOnlyHint`. Com `APPROVAL_REQUIRED_FOR_MUTATING_TOOLS=true`:

1. O `/chat` não executa a chamada; ele retorna `pending_approvals` com o `id`.
2. Um admin lista as pendências em `GET /approvals` e aprova (ou rejeita) aquela chamada exata com `POST /approvals/{id}` e o corpo `{"approve": true}`.
3. O usuário pede ao agente para repetir a chamada, que roda uma única vez com os mesmos argumentos.

O cliente não pode se autoaprovar (não existe campo `approved` no `/chat`).

## MCP

`POST /mcp/servers` (somente admin) com `{"name","url","prefix"}`:

- Nome duplicado retorna 409; servidor inalcançável retorna 502.
- Os servidores registrados são recarregados na inicialização. Falhas nessa recarga aparecem no log como `mcp_import_failed`.

## Sandbox

- A ferramenta `shell` aceita apenas `ls pwd cat head tail wc find grep stat du df`, sem `awk`/`sed`.
- Flags que executam, escrevem ou seguem symlinks são bloqueadas (`find -exec/-delete/-L`, `grep -R` etc.).
- Todo argumento de caminho precisa ficar dentro de `SANDBOX_ROOT`.
- O processo roda sem as variáveis de ambiente do harness.

## CI / Git

- O `CI` roda os testes unitários e o job `e2e`, que executa a stack completa via Compose e o `e2e/smoke.py --restart`.
- Tags `v*` publicam a imagem no GHCR.

## Antes de produção

- Trocar o login local por OIDC/Entra/Keycloak.
- Usar Alembic.
- Criar um índice HNSW em `document_chunks.embedding`.
- Isolar execução mutável em sandbox efêmero.
- Colocar secrets em secret manager.
- Backup do PostgreSQL.
- Rate limiting no login.
- Métricas/OTel.
- Política de egress.
- Fazer pin de imagens (`ollama/ollama:latest`) e dependências.
