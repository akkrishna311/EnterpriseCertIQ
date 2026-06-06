# EnterpriseCertIQ backend — FastAPI + in-process agent runtime + MCP tools.
# Build:  docker build -t enterprisecertiq-backend .
# Run:    docker run -p 8000:8000 --env-file .env.azure enterprisecertiq-backend
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; reportlab needs no native libs on slim for our usage.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching.
# Azure deploys should use the cloud requirements (adds azure-* SDKs).
COPY requirements.txt requirements.azure.txt ./
ARG INSTALL_AZURE=true
RUN if [ "$INSTALL_AZURE" = "true" ]; then \
        pip install -r requirements.azure.txt ; \
    else \
        pip install -r requirements.txt ; \
    fi

# App code
COPY backend/ ./backend/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY scripts/ ./scripts/

# Container Apps / App Service inject $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

# Foundry Local is a dev-only backend; containers should run MODEL_BACKEND=azure_foundry.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
