# Container for the Option-A OSS A2A app (service.oss.app), for Cloud Run.
# This is the partner-hosted A2A endpoint Gemini Enterprise talks to; it is the
# path that can emit the interactive "A2-UI" upgrade-choice element.
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps first (cache-friendly). httpx is needed by the rest client
# and is only a dev extra in pyproject, so install it explicitly.
COPY pyproject.toml README.md ./
COPY service ./service
COPY agent-card-oss.json ./agent-card-oss.json
RUN pip install --no-cache-dir . httpx

ENV PORT=8080
# Rule-based router (no model key needed); emit the A2UI v0.9 interactive surface
# (Gemini Enterprise's GA UI protocol) for upgrade choices.
ENV OSS_ROUTER=rule OSS_CLIENT=mock OSS_UI_PROTOCOL=a2ui
EXPOSE 8080
CMD exec uvicorn service.oss.app:app --host 0.0.0.0 --port ${PORT}
