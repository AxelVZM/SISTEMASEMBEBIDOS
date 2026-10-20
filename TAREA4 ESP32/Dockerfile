FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ORBITA_DB_PATH=/datos/orbita.sqlite3
WORKDIR /app
COPY servidor/requirements.txt /app/servidor/requirements.txt
RUN pip install --no-cache-dir -r servidor/requirements.txt && useradd --uid 10001 --create-home orbita && mkdir /datos && chown orbita:orbita /datos
COPY servidor /app/servidor
COPY web /app/web
USER orbita
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "30", "--access-logfile", "-", "servidor.wsgi:app"]
