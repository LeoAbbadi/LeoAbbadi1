#!/usr/bin/env bash
# Roda uma vez, quando o Codespace é criado: instala FFmpeg e Postgres,
# cria o banco, configura o .env de teste, instala e compila o site.
set -euo pipefail
cd "$(dirname "$0")/../facilitador-tiktok-shop"

sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg postgresql
sudo service postgresql start

sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='fts'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER fts WITH PASSWORD 'fts' CREATEDB;"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='fts'" | grep -q 1 \
  || sudo -u postgres createdb -O fts fts

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^SESSION_SECRET=.*/SESSION_SECRET=$(openssl rand -hex 32)/" .env
  # modo de teste: o site também monta os vídeos e os planos ativam sem cobrar
  sed -i "s/^EMBEDDED_WORKER=.*/EMBEDDED_WORKER=true/" .env
  sed -i "s/^DEMO_BILLING=.*/DEMO_BILLING=true/" .env
  # guarda os vídeos prontos só por 2 dias, para não gastar o espaço grátis
  sed -i "s/^OUTPUT_RETENTION_DAYS=.*/OUTPUT_RETENTION_DAYS=2/" .env
fi

npm ci
npm run build
npm run seed
echo "Pronto. O site liga sozinho no terminal (porta 3000)."
