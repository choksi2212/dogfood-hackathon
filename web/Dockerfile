FROM node:22-alpine

WORKDIR /app

# Layer-cached: install deps first so source edits don't bust this.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --prefer-offline

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

# Dev server — matches the rest of the stack (Django also runs its
# dev server, not gunicorn, per docker-compose.yml). Swap to
# `npm run build && npm start` for a production image.
CMD ["npm", "run", "dev"]
