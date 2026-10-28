FROM python:3.11-alpine

WORKDIR /app

COPY server.py ./
COPY public ./public
COPY config.example.json ./config.example.json

EXPOSE 8095

ENV HOST=0.0.0.0
ENV PORT=8095
ENV RO3_DB_PATH=/data/ro3emu.db
ENV RO3_STATUS_URL=http://ro3emu:5380/ro3emu/status

CMD ["python", "server.py"]
