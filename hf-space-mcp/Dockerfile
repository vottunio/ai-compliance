FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache git \
 && git clone --depth 1 https://github.com/vottunio/ai-compliance.git /tmp/repo \
 && cp -r /tmp/repo/mcp-server/. /app/ \
 && rm -rf /tmp/repo \
 && apk del git

RUN npm ci --omit=dev

ENV PORT=7860
EXPOSE 7860

CMD ["node", "server.js"]
