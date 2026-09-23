FROM python:3.12-slim
WORKDIR /srv
RUN useradd -m -u 10001 appuser
COPY requirements.txt .
# Optional corporate/proxy CA for pip: `docker build --secret id=pip_ca,src=/path/ca.crt .`
# Without the secret this is a plain pip install; the CA is never stored in the image.
RUN --mount=type=secret,id=pip_ca,required=false \
    if [ -s /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /workspace && chown appuser:appuser /workspace
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
