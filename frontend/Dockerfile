###############################################
# Elion MDM - Frontend
# Stage 1: build React/Vite
# Stage 2: serve bundle estatico em Node.js
###############################################

# -- Stage 1: build ---------------------------
FROM node:20-alpine AS build

WORKDIR /app

# COPY package*.json para cache eficiente
COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# -- Stage 2: producao ------------------------
FROM node:20-alpine AS production

WORKDIR /app

RUN npm install -g serve

COPY --from=build /app/dist ./dist

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["serve", "-s", "dist", "-l", "3000"]

# -- Stage dev (selecionada por target no compose) --
FROM node:20-alpine AS development

WORKDIR /app

# Instalar dependencias para dev (permite hot reload no volume)
COPY package.json package-lock.json* ./
RUN npm install

# O codigo sera montado via volume no compose, mas mantemos o COPY
COPY . .

EXPOSE 3000

# Healthcheck para o compose monitorar o Vite
HEALTHCHECK --interval=20s --timeout=10s --retries=5 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
