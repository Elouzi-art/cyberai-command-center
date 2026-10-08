FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir . && mkdir /data && chown 10001 /data
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
