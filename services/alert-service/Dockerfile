FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app:/libs

COPY services/alert-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /libs/shared
COPY services/alert-service .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
