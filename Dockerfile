# Use a lightweight Python base image
FROM python:3.11-slim

# Install system dependencies including curl and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    libmagic-dev \
    curl \
    libmagic1 \
 && rm -rf /var/lib/apt/lists/*

# Install the latest yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY . .

# Ensure cookies directory exists if needed
RUN mkdir -p /mnt/data

# Expose port for Flask app
EXPOSE 8000

# Start the Flask app
CMD ["python", "restream.py"]
