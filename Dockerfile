FROM python:3.11-slim

# Install Node.js (needed for Elastic MCP server)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Elastic MCP server globally
RUN npm install -g @elastic/mcp-server-elasticsearch

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Cloud Run uses port 8080
ENV PORT=8080

EXPOSE 8080

CMD ["python", "server.py"]
