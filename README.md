# Ferrioli Tráfego Core API

Infraestrutura inicial do SaaS de gestao de trafego, baseada em FastAPI, PostgreSQL e Redis, preparada para evolucao em ambiente containerizado.

## Tecnologias base

- FastAPI
- PostgreSQL 15
- Redis
- Docker / Docker Compose

## Configuracao inicial

1. Copie o arquivo de exemplo de ambiente:

```bash
cp .env.example .env
```

2. Preencha o arquivo `.env` com os valores reais de ambiente.

## Subindo os servicos

```bash
docker-compose up -d --build
```

Isso iniciara os servicos:

- `db` (PostgreSQL)
- `redis`
- `api` (imagem da aplicacao FastAPI)

## Proximos passos

- Criar a estrutura da aplicacao FastAPI (`app/`).
- Definir configuracoes centralizadas (settings com Pydantic).
- Implementar conexao com banco e filas.
