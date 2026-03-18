###############################################
# Elion MDM – Frontend
# Stage 1: build React/Vite
# Stage 2: servir via Nginx (produção)
# Dev override usa apenas Stage 1 + npm run dev
###############################################

# ── Stage 1: build ───────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: produção (Nginx serve /dist) ────
FROM nginx:alpine AS production

# Remove config default
RUN rm /etc/nginx/conf.d/default.conf

# Config simples para servir SPA
COPY --from=build /app/dist /usr/share/nginx/html

# Fallback para rotas SPA (React Router)
RUN printf 'server {\n\
    listen 3000;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

# ── Stage dev (selecionada por target no compose) ─
FROM node:20-alpine AS development

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
