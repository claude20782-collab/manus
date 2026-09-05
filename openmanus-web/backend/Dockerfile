FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install system dependencies
USER root
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    build-essential \
    curl \
    git \
    libatlas-base-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Create non-root user for security
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
