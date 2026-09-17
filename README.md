# API de Almoxarifado

API REST para controle de estoque de um almoxarifado de pequena empresa: cadastro de produtos, entradas, saídas e ajustes de inventário, alerta de estoque mínimo, perfis de acesso e trilha de auditoria.

Documentação interativa: https://api-almoxarifado.vercel.app/docs

Na página `/docs`, clique em **Authorize** e entre com uma conta de demonstração:

| Perfil | Email | Senha |
|---|---|---|
| operador | `operador@demo.dev` | `demo-operador-2026` |
| leitura | `leitura@demo.dev` | `demo-leitura-2026` |

Os dados voltam ao original todo dia às 3h (horário de Brasília).

## O problema

Em almoxarifado pequeno o controle costuma ficar numa planilha que várias pessoas editam. Ninguém sabe quem tirou o quê, o saldo fica negativo quando duas pessoas registram saída ao mesmo tempo e o material acaba antes de alguém perceber.

A API resolve isso com três regras:

- **Saldo só muda por movimentação.** Não existe endpoint pra editar a quantidade direto. Entrada soma, saída subtrai e ajuste de inventário define o valor contado, sempre com uma nota explicando.
- **Saldo nunca fica negativo.** A saída trava a linha do produto (`SELECT ... FOR UPDATE`) antes de conferir o saldo, e o banco ainda tem uma `CHECK (quantity >= 0)`. Tem teste no CI com duas saídas simultâneas no PostgreSQL.
- **Tudo fica registrado.** Cada movimentação, alteração de produto, criação de usuário e tentativa de login que falhou vai pra tabela de auditoria, com quem fez, quando e o valor antes e depois.

## Perfis

| | leitura | operador | admin |
|---|:-:|:-:|:-:|
| Consultar produtos, histórico e relatórios | sim | sim | sim |
| Registrar entrada, saída e ajuste | | sim | sim |
| Cadastrar e editar produtos | | | sim |
| Gerenciar usuários e ver auditoria | | | sim |

## Endpoints

| Método | Rota | Perfil mínimo |
|---|---|---|
| POST | `/auth/token` | público |
| GET | `/auth/me` | leitura |
| GET | `/products?search=&below_minimum=&page=&page_size=` | leitura |
| POST | `/products` | admin |
| GET / PATCH | `/products/{id}` | leitura / admin |
| POST | `/products/{id}/movements` | operador |
| GET | `/products/{id}/movements` | leitura |
| GET | `/reports/low-stock` | leitura |
| GET | `/reports/summary` | leitura |
| GET / POST | `/users` | admin |
| PATCH | `/users/{id}` | admin |
| GET | `/audit-logs` | admin |

## Stack

- Python 3.13, FastAPI, Pydantic
- SQLAlchemy 2 e Alembic (migrations)
- PostgreSQL (Supabase em produção)
- JWT com PyJWT e senhas com Argon2 (pwdlib)
- pytest, Ruff, uv
- Docker e docker-compose
- GitHub Actions: lint, testes em SQLite e em PostgreSQL, migrations subindo e descendo, build e teste do container
- Deploy na Vercel

## Rodando

Com Docker:

```bash
cp .env.example .env   # preencha JWT_SECRET e POSTGRES_PASSWORD
docker compose up --build
```

A API sobe em http://localhost:8000/docs e aplica as migrations sozinha.

Sem Docker (usa SQLite):

```bash
uv sync --group dev
cp .env.example .env
uv run alembic upgrade head
uv run python -m app.seed      # precisa de ADMIN_PASSWORD no .env
uv run uvicorn app.main:app --reload
```

Testes:

```bash
uv run pytest
```

Os testes rodam em SQLite por padrão. Com `TEST_DATABASE_URL` apontando pra um PostgreSQL, rodam lá também, incluindo o de concorrência.

## Segurança

- Senhas com Argon2; o login responde igual pra email inexistente e senha errada, e gasta o mesmo tempo nos dois casos
- 5 tentativas erradas por IP e email bloqueiam o login por 5 minutos
- Token JWT com expiração de 30 minutos. Papel e status do usuário são lidos do banco a cada requisição, então desativar alguém corta o acesso na hora
- Todo corpo de requisição é validado com Pydantic e campo desconhecido é recusado: não dá pra mandar `quantity` num PATCH de produto nem `role` no cadastro
- Consultas só pelo ORM, sem SQL montado com texto
- Respostas com modelo explícito, sem `password_hash` nem stack trace; erro de validação não devolve o valor enviado
- Headers de segurança e CSP; corpo da requisição limitado a 32 KB
- No banco de produção a API usa um usuário próprio com acesso só ao schema dela
- Segredos só em variável de ambiente; a senha do admin da demonstração não é pública
- Actions fixadas por hash de commit e `pip-audit` no CI

## Estrutura

```
app/
  main.py          app, headers, tratamento de erros
  config.py        configuracao por variavel de ambiente
  models.py        tabelas
  schemas.py       entrada e saida da API
  security.py      senha, JWT e perfis
  stock.py         regra de movimentacao de estoque
  audit.py         trilha de auditoria
  ratelimit.py     limite de tentativas de login
  seed.py          dados de demonstracao
  routers/         auth, products, reports, users
alembic/           migrations
tests/
```
