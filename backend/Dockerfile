FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-build the matplotlib font cache at image-build time. Without this the
# first cell that touches matplotlib pays a 15-30s one-off cache build inside
# a fresh container, which trips the per-cell execution timeout.
ENV MPLCONFIGDIR=/tmp/mpl
RUN mkdir -p /tmp/mpl && python -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; plt.plot([1,2,3]); import pandas, numpy"

COPY . .

# Render sets $PORT at runtime and requires the service to bind to it on 0.0.0.0.
# Do not hardcode a port here.
# Single worker + threads: the in-process WorkerManager keeps each session's
# execution process, so sessions must stay affine to one Gunicorn worker.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120 wsgi:app"]
