# Base image: Node 24 on Debian Bookworm
FROM node:24-bookworm

# Install Python 3.12+ (bookworm defaults to 3.11, but it's sufficient for Playwright), pip, and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    libgbm-dev \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Set up pnpm
RUN npm install -g pnpm@10.33.2

# Install global opencode-ai CLI (required by user workflow)
RUN npm install -g opencode-ai

# Set working directory
WORKDIR /app

# Copy the entire workspace
COPY . .

# Install JS dependencies and build the daemon
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @open-design/daemon... build

# Create a proper Linux .venv and install Python dependencies into it.
# The daemon's resolvePythonBin() looks for /app/.venv/bin/python first.
RUN python3 -m venv /app/.venv
RUN /app/.venv/bin/pip install --upgrade pip
RUN /app/.venv/bin/pip install playwright nest_asyncio

# Install Playwright browsers (Chromium) — uses the venv's playwright
RUN /app/.venv/bin/python -m playwright install --with-deps chromium

# Expose the daemon port
EXPOSE 7456

# Default entrypoint for the container
CMD ["node", "apps/daemon/dist/cli.js"]
