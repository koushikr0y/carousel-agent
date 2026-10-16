FROM python:3.12-slim

# Install system dependencies required for headless Firefox & Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    git \
    fonts-liberation \
    fonts-noto-color-emoji \
    libgtk-3-0 \
    libasound2 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps firefox

# Copy project code
COPY . .

# Run the Telegram Bot runner
CMD ["python", "main.py", "bot"]
