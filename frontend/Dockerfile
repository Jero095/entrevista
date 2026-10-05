# 1) Compilación: TypeScript estricto + Vite generan archivos estáticos en /app/dist.
FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# La API key de desarrollo se incluye en el bundle para la demo (ver README).
ARG VITE_API_KEY=""
ENV VITE_API_KEY=$VITE_API_KEY
RUN npm run build

# 2) Servidor: nginx sirve los estáticos y reenvía /api, /health y /docs a la API.
FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
