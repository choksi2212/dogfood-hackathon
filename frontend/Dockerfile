FROM node:22-alpine

WORKDIR /app

# Layer-cached: install deps first so source edits don't bust this.
COPY package.json ./
RUN npm install --no-audit --no-fund --prefer-offline

# Source. Mihir replaces this layer.
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

# Dev server. For prod, swap to ``npm run build && npm start``.
CMD ["npm", "run", "dev"]
