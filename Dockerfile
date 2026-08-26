# ============================================================
# WOJAN STUDIO — obraz produkcyjny
# Zero zależności runtime (czysty Node.js), mały obraz alpine.
# ============================================================
FROM node:20-alpine

# Katalog roboczy
WORKDIR /app

# Najpierw pliki projektu (bez node_modules — nie są potrzebne)
COPY package.json ./
COPY server.js ./
COPY public ./public

# Dane (baza + media) montujemy jako wolumen na zewnątrz,
# ale tworzymy katalog, żeby aplikacja miała gdzie pisać.
RUN mkdir -p /app/data/media

# Użytkownik nie-root (bezpieczeństwo)
RUN addgroup -S wojan && adduser -S wojan -G wojan \
    && chown -R wojan:wojan /app
USER wojan

ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

EXPOSE 3000

# Healthcheck — endpoint /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1

CMD ["node", "server.js"]
