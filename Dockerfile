FROM python:3.10-slim

# Avoid Python writing .pyc files and set unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build deps required for some scientific packages (scipy/numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    ca-certificates \
    wget \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY cvp-sphere-api/requirements.txt ./cvp-sphere-api/requirements.txt

RUN pip install --upgrade pip
RUN pip install -r cvp-sphere-api/requirements.txt

# Copy the rest of the repo
COPY . /app

EXPOSE 8000

# Use the existing start script
CMD ["bash", "start.sh"]
