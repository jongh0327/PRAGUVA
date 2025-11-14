FROM php:8.2-apache

# Install Python
RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

# Enable Apache rewrite
RUN a2enmod rewrite

WORKDIR /var/www/html

# Copy project files into container
COPY . /var/www/html/

# Create Python virtual environment outside the web root
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies inside the venv
RUN /bin/bash -c "\
    source /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r python/requirements.txt && \
    python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"all-MiniLM-L6-v2\")' \
"

# Make uploads writable
RUN mkdir -p /var/www/html/uploads && chmod -R 777 /var/www/html/uploads

# Expose Apache
EXPOSE 80