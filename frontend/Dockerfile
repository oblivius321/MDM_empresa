FROM node:20-alpine

WORKDIR /app

# Instalar dependências primeiro para cache do Docker
COPY package*.json ./
RUN npm install

# Copiar resto do código
COPY . .

# Expor porta 3000 do Vite
EXPOSE 3000

# Rodar em modo de desenvolvimento atado ao host
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
