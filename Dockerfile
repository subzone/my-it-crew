FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY tests/ tests/

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1

# Default: run single agent worker (set AGENT_ID env var)
# For legacy orchestrator mode: override CMD
CMD ["python", "-m", "src.orchestrator.worker"]
