FROM node:20-alpine

WORKDIR /app

ADD https://api.github.com/repos/vottunio/ai-compliance/git/refs/heads/main /tmp/version.json

RUN apk add --no-cache git \
 && git clone --depth 1 https://github.com/vottunio/ai-compliance.git /tmp/repo \
 && cp -r /tmp/repo/mcp-server/. /app/ \
 && cp /tmp/repo/SKILL.md /SKILL.md \
 && rm -rf /tmp/repo \
 && apk del git

RUN npm ci --omit=dev

ENV PORT=7860
ENV ALLOWED_HOSTS=sergimima-aiact50-mcp.hf.space,localhost,127.0.0.1
EXPOSE 7860

CMD ["node", "server.js"]
