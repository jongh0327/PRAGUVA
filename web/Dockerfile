FROM php:8.2-apache

# Install Python
RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

# Enable Apache rewrite
RUN a2enmod rewrite

WORKDIR /var/www/html

# Copy only requirements first (cache pip install layer)
COPY python/requirements.txt ./python/requirements.txt

# Create Python virtual environment outside web root
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies inside the venv
RUN /bin/bash -c "\
    source /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r python/requirements.txt && \
    python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"all-MiniLM-L6-v2\")' \
"

# Copy the rest of your project
COPY . /var/www/html/

# Make uploads writable
RUN mkdir -p /var/www/html/uploads && chmod -R 777 /var/www/html/uploads

# Expose Apache
EXPOSE 80