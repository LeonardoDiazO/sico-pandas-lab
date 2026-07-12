FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime and requires the service to bind to it on 0.0.0.0.
# Do not hardcode a port here.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} wsgi:app"]
