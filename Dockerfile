FROM python:3.11-slim

WORKDIR /app

# System deps for faiss-cpu and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the instance directory exists for SQLite (volume mount may overlay it,
# but the directory must exist in the image for the first-run case)
RUN mkdir -p /app/instance

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
