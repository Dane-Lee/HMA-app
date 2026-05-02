# Stage 1: build the React frontend
FROM node:20-slim AS web-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python API + built frontend
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY api/requirements.txt api/requirements-vision.txt ./api/
RUN pip install --no-cache-dir -r api/requirements.txt -r api/requirements-vision.txt

COPY api/ api/
COPY config/ config/
COPY --from=web-builder /web/dist web/dist

COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 443

ENTRYPOINT ["./entrypoint.sh"]
