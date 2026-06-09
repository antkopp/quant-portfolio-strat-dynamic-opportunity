FROM python:3.12-slim

ARG GITHUB_TOKEN

WORKDIR /app

RUN apt-get update && apt-get install -y git gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" \
    && pip install --no-cache-dir -r requirements.txt \
    && git config --global --unset url."https://${GITHUB_TOKEN}@github.com/".insteadOf

COPY . .

CMD ["python", "entrypoint.py"]
