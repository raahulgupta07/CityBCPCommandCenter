FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-dotenv requests

COPY . .

# Pre-seed DB during build (backup copy for first-run)
RUN mkdir -p db db_seed && python seed_database.py && cp db/bcp.db db_seed/bcp.db && rm -f db/bcp.db db/bcp.db-wal db/bcp.db-shm

RUN chmod +x entrypoint.sh

EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1
ENTRYPOINT ["./entrypoint.sh"]
