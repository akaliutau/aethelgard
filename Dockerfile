# Use the official Python 3.12 slim image to minimize image size
FROM python:3.12-slim

# Prevent Python from writing .pyc files to disk and ensure logs flush immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set the working directory inside the container
WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Copy ONLY the optimized server requirements
COPY requirements-server.txt .

# Install core server dependencies (no ML libraries)
RUN pip install --no-.cache-dir -r requirements-server.txt

# Selectively copy only the necessary files/folders to run the Orchestrator
COPY aethelgard/ ./aethelgard/
COPY profiles/ ./profiles/
COPY samples/02_production_server.py ./samples/02_production_server.py

# Create a non-root user for security
RUN useradd -m aetheluser && chown -R aetheluser /app
USER aetheluser

# Expose the default FastAPI port
EXPOSE 8010

# Boot the central orchestrator
CMD ["python", "samples/02_production_server.py", "--config", "profiles/server.env"]