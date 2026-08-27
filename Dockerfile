# Base Python image
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install curl, Node.js, and npm (required for `npx 3gpp-mcp-charging` stdio subprocess)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (leverage Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-fetch the 3GPP MCP npm package so cold-starts are faster
RUN npx --yes 3gpp-mcp-charging@latest --help || true

# Copy application source code
COPY app/ ./app/

# Render sets the PORT environment variable (default fallback to 8000)
ENV PORT=8000
EXPOSE 8000

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT provided by Render
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
