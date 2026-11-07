FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.9.30 \
    && useradd --create-home --uid 1000 app

WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY data ./data

USER app
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
