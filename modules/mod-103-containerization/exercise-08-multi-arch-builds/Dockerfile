# syntax=docker/dockerfile:1.6
# Multi-arch (amd64 + arm64) iris-api image.
ARG TARGETPLATFORM
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py model.json ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
