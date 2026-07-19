FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system workflowtwin \
    && adduser --system --ingroup workflowtwin workflowtwin

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY data ./data
RUN pip install --no-cache-dir .

USER workflowtwin
EXPOSE 8000

CMD ["uvicorn", "workflowtwin.main:app", "--host", "0.0.0.0", "--port", "8000"]
