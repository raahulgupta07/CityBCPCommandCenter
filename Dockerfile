FROM python:3.12-slim

# Set timezone to Myanmar (UTC+6:30)
ENV TZ=Asia/Yangon
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-dotenv requests

COPY . .

# Create DB directory (empty — user uploads all data via UI)
RUN mkdir -p db

RUN chmod +x entrypoint.sh

EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1
ENTRYPOINT ["./entrypoint.sh"]
