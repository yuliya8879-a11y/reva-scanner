FROM python:3.11-slim

WORKDIR /app

# Install deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Railway injects $PORT at runtime
ENV PORT=8000

EXPOSE $PORT

RUN chmod +x start.sh
CMD ["sh", "start.sh"]
