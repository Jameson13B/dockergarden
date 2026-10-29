FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/Jameson13B/dockergarden" \
      org.opencontainers.image.description="Your Docker containers as an ASCII garden in the terminal."

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TERM=xterm-256color \
    COLORTERM=truecolor

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENTRYPOINT ["garden"]
