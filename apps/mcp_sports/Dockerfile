# Build context must be the REPO ROOT:
#   docker build -f apps/mcp_sports/Dockerfile -t mcp-sports .
FROM python:3.11-slim

WORKDIR /app

# Install shared package first (it is a pure-python dep)
COPY packages/shared_py /app/packages/shared_py
RUN pip install --no-cache-dir /app/packages/shared_py

# Install app dependencies + the app itself
COPY apps/mcp_sports /app/apps/mcp_sports
RUN pip install --no-cache-dir /app/apps/mcp_sports

# Server entry-point lives at the top of the app directory
WORKDIR /app/apps/mcp_sports

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8765

EXPOSE 8765

CMD ["python", "server.py"]
