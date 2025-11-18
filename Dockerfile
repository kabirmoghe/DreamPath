FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files (from project root)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy backend code
COPY backend/ ./backend/

# Set working directory to backend
WORKDIR /app/backend

# Expose port 8080 (Fly.io will set PORT env var to 8080)
EXPOSE 8080

# Run the application
CMD ["uv", "run", "python", "run_service.py"]
