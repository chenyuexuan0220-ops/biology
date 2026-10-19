FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .
COPY migrations ./migrations
COPY alembic.ini ./
COPY seed ./seed
COPY prompts ./prompts
COPY scripts ./scripts
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python scripts/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
