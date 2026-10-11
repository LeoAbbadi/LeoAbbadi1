# Publicando o site

Arquitetura recomendada para começar (simples e barata):

| Peça | Serviço | Para quê |
|---|---|---|
| Site + API | Railway (serviço "api", `Dockerfile`) | páginas, login, pagamentos |
| Worker de vídeo | Railway (serviço "worker", `Dockerfile.worker`) | FFmpeg monta os vídeos |
| Banco | Railway Postgres | usuários, projetos, fila |
| Arquivos | Cloudflare R2 | pedaços e vídeos prontos (download grátis) |
| Pagamento | Stripe | assinaturas com cartão; Pix no anual |
| IA | Anthropic (Claude) | roteiros |

## Passo a passo

1. **Railway**: crie um projeto ligado a este repositório e adicione um Postgres.
   - Serviço `api`: Dockerfile `Dockerfile`, porta 3000, domínio público.
   - Serviço `worker`: Dockerfile `Dockerfile.worker`, sem domínio. Comece com 2 vCPU e 2 GB.
   - Nos dois, configure as variáveis do `.env.example` (a `DATABASE_URL` vem do Postgres).
   - O banco é criado sozinho na primeira subida (migrações automáticas).
2. **Cloudflare R2**: crie um bucket e uma chave de API (Access Key + Secret).
   - `STORAGE_DRIVER=s3`, `S3_ENDPOINT=https://<conta>.r2.cloudflarestorage.com`,
     `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION=auto`.
   - Libere o CORS do bucket para o navegador enviar e baixar direto:
     ```json
     [{ "AllowedOrigins": ["https://seu-dominio.com.br"], "AllowedMethods": ["PUT", "GET", "HEAD"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 3600 }]
     ```
3. **Stripe**: crie 3 preços recorrentes (Criador mensal R$ 49, Pro mensal R$ 89,
   Pro anual R$ 597) e coloque os IDs `price_...` em `STRIPE_PRICE_*`.
   - Webhook para `https://seu-dominio.com.br/api/billing/webhook` com os eventos
     `customer.subscription.created`, `.updated` e `.deleted`. O segredo vai em `STRIPE_WEBHOOK_SECRET`.
   - Ative o Portal do Cliente (para o usuário cancelar sozinho).
   - Se preferir Pix recorrente, Asaas, Pagar.me e Mercado Pago são alternativas; só o
     arquivo `src/server/routes/billing.ts` muda.
4. **Anthropic**: crie a chave em console.anthropic.com e coloque em `ANTHROPIC_API_KEY`.
5. **Admin**: coloque seu e-mail em `ADMIN_EMAILS` para ver a área de importação de produtos.
6. **Domínio**: aponte o domínio para o serviço `api` e ajuste `APP_URL`.

## Crescendo

- Mais clientes gerando ao mesmo tempo → aumente as réplicas do `worker` ou
  `WORKER_CONCURRENCY`. Cada lote de 150 vídeos ocupa ~1 vCPU por ~3 minutos.
- Banco ficando grande → os vídeos vencidos já são apagados sozinhos (`OUTPUT_RETENTION_DAYS`).
