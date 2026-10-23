ARG NODE_BASE_IMAGE=node:22-bookworm-slim
FROM ${NODE_BASE_IMAGE}

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund \
    && cp package-lock.json node_modules/.cloudvault-package-lock.json

COPY . .
COPY docker-entrypoint.sh /usr/local/bin/cloudvault-frontend-entrypoint

EXPOSE 5173

ENTRYPOINT ["sh", "/usr/local/bin/cloudvault-frontend-entrypoint"]
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]