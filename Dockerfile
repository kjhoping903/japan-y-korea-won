FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV BIND_HOST=0.0.0.0 PORT=8000 DB_PATH=/data/fx.sqlite3
EXPOSE 8000
CMD ["python", "container_start.py"]
