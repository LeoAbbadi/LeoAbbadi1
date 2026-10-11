#!/usr/bin/env bash
# Roda toda vez que você abre o Codespace: liga o banco e o site (com o worker de vídeo).
# Deixe este terminal aberto enquanto testa. Para parar: Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/../facilitador-tiktok-shop"
sudo service postgresql start >/dev/null
echo ""
echo "  Facilitador ligado. Abra a aba PORTAS (Ports) e clique no globo da porta 3000."
echo "  Conta de teste: demo@facilitador.local / demo12345 (plano Pro)"
echo ""
exec npx tsx --env-file=.env src/server/index.ts
