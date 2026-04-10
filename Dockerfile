FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["bash", "docker-entrypoint.sh"]
