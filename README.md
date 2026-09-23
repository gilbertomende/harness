# AI Harness — Stage v0.2.0

Harness FastAPI independente de provedor com sessão PostgreSQL, agent loop, tool registry, Ollama/OpenRouter/9Router, RAG/pgvector, MCP, sandbox, JWT/RBAC, auditoria e fallback automático de modelos.

## Topologia recomendada

Local: Docker Desktop/Compose para desenvolvimento e smoke tests.
Stage/produção: VPS Ubuntu LTS + Docker Engine/Compose + reverse proxy TLS. Mantenha PostgreSQL, harness e Ollama em rede privada. Exponha somente HTTPS do reverse proxy.
Vercel: opcional para um frontend Next.js; não é o destino recomendado para o backend stateful deste harness.

## Stage

1. `cp .env.example .env`
2. Troque JWT_SECRET, ADMIN_PASSWORD, POSTGRES_PASSWORD e DATABASE_URL.
3. `docker compose -f compose.stage.yaml --profile local-model up -d --build`
4. `docker compose -f compose.stage.yaml exec ollama ollama pull qwen3:8b`
5. `docker compose -f compose.stage.yaml exec ollama ollama pull nomic-embed-text`
6. `curl http://127.0.0.1:8000/health`

Login:
`curl -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"SUA-SENHA"}'`

Use o token Bearer em `/chat`, `/rag/*` e `/mcp/*`.

## Model router

`DEFAULT_PROVIDER=auto` tenta Ollama -> 9Router -> OpenRouter. `private=true` restringe a chamada ao Ollama. Também é possível fixar `provider` e `model` por request.

`private=true` só aceita provider local (Ollama); pedir `provider=openrouter`/`9router` com `private=true` retorna 403.

## Aprovação de ferramentas mutáveis

Ferramentas MCP são tratadas como mutáveis, exceto as que o servidor declara `readOnlyHint`. Com `APPROVAL_REQUIRED_FOR_MUTATING_TOOLS=true`, o `/chat` não executa a chamada: ele retorna `pending_approvals` com o `id`. Um admin aprova (ou rejeita) aquela chamada exata com `POST /approvals/{id}` `{"approve": true}` e lista as pendências em `GET /approvals`. Depois o usuário pede ao agente para repetir a chamada, que roda uma única vez com os mesmos argumentos. O campo `approved` do `/chat` foi removido; o cliente não se autoaprova.

## Sandbox

A ferramenta `shell` aceita apenas `ls pwd cat head tail wc find grep stat du df`, sem `awk`/`sed`. Flags que executam, escrevem ou seguem symlinks (`find -exec/-delete/-L`, `grep -R` etc.) são bloqueadas, todo argumento de caminho precisa ficar dentro de `SANDBOX_ROOT`, e o processo roda sem as variáveis de ambiente do harness.

## Git

`CI` valida Python, testes (`pip install -r requirements-dev.txt && pytest`) e build Docker. Tags `v*` publicam a imagem no GHCR.

## Antes de produção

Trocar o login local por OIDC/Entra/Keycloak; usar Alembic; isolar execução mutável em sandbox efêmero; colocar secrets em secret manager; backup PostgreSQL; rate limiting; TLS; métricas/OTel; política de egress; pin de imagens e dependências; testes de integração para cada provider/MCP.
