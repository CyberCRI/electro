FROM python:3.12.6-slim AS builder

ARG EXPORT_FLAG="--with dev"

RUN pip install --upgrade pip poetry poetry-plugin-export

COPY pyproject.toml poetry.lock ./

RUN poetry export -f requirements.txt $EXPORT_FLAG --without-hashes --output /tmp/requirements.txt


FROM python:3.12.6-slim
  
WORKDIR /app

RUN groupadd -g 10000 app && \
  useradd -g app -d /app -u 10000 app && \
  chown app:app /app && \
  apt-get update && \
  apt upgrade -y && \
  apt-get install nano && \
  apt-get install -y git && \
  pip install --upgrade pip

COPY --from=builder /tmp/requirements.txt .

RUN pip install -r requirements.txt
RUN pip install watchdog

COPY . .

USER app
ENV PYTHONPATH="/app"

CMD ["watchmedo", "auto-restart", "--pattern=*.py", "--recursive", "--", "python", "main.py"]