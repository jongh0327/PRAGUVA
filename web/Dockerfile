FROM php:8.2-apache

# Install system packages
RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

# Install PHP sockets extension
RUN docker-php-ext-install sockets

# Enable Apache rewrite
RUN a2enmod rewrite

WORKDIR /var/www/html

# ====== DEPENDENCY LAYER (cached unless requirements.txt changes) ======
# Copy only requirements first
COPY python/requirements.txt /tmp/requirements.txt

# Create Python virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies (this layer is cached!)
RUN /bin/bash -c "\
    source /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"all-MiniLM-L6-v2\")' \
"

# ====== APPLICATION CODE LAYER (changes frequently, doesn't affect deps) ======
# Copy scripts first (less likely to change)
COPY start_services.sh /usr/local/bin/start_services.sh
COPY manage_llm_server.sh /usr/local/bin/manage_llm_server.sh
RUN chmod +x /usr/local/bin/start_services.sh /usr/local/bin/manage_llm_server.sh

# Create directories
RUN mkdir -p /var/www/html/uploads && chmod -R 777 /var/www/html/uploads
RUN mkdir -p /var/log && chmod 777 /var/log

# Copy the rest of your project LAST (changes most frequently)
COPY . /var/www/html/

# Expose Apache
EXPOSE 80

# Use custom startup script
CMD ["/usr/local/bin/start_services.sh"]