FROM python:3.12-slim
WORKDIR /srv
RUN useradd -m -u 10001 appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /workspace && chown -R appuser:appuser /workspace /srv
USER appuser
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
