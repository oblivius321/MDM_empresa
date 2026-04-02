###############################################
# Elion MDM – Frontend
# Stage 1: build React/Vite
# Stage 2: servir via Nginx (produção)
###############################################

# ── Stage 1: build ───────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# COPY package*.json para cache eficiente
COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# ── Stage 2: produção (Nginx serve /dist) ────
FROM nginx:alpine AS production

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# SPA fallback configuration
RUN printf 'server {\n\
    listen 3000;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

# ── Stage dev (selecionada por target no compose) ─
FROM node:20-alpine AS development

WORKDIR /app

# Instalar dependências para dev (permite hot reload no volume)
COPY package.json package-lock.json* ./
RUN npm install

# O código será montado via volume no compose, mas mantemos o COPY
COPY . .

EXPOSE 3000

# Healthcheck para o compose orquestrar o Nginx
HEALTHCHECK --interval=20s --timeout=10s --retries=5 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
