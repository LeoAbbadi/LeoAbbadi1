# Site + API. Em produção o mesmo processo entrega o site (dist) e a API.
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist
COPY src ./src
COPY db ./db
EXPOSE 3000
CMD ["npx", "tsx", "src/server/index.ts"]
