# Site + API. Em produção o mesmo processo entrega o site (dist) e a API.
# Com EMBEDDED_WORKER=true ele também monta os vídeos.
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim
# FFmpeg incluído para poder rodar com EMBEDDED_WORKER=true (site + worker num serviço só)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist
COPY src ./src
COPY db ./db
EXPOSE 3000
CMD ["npx", "tsx", "src/server/index.ts"]
