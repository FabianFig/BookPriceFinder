FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir .[web] && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["bookfinder", "web", "--host", "0.0.0.0", "--port", "8000"]
