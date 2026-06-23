FROM python:3.11-slim

# ffmpeg (with libass) is needed by the clip + caption stages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY services ./services

# Install with the transcribe extra so the clip + caption stages work in the
# container (faster-whisper). Drop the extra for a lighter API-only image.
RUN pip install --no-cache-dir -e ".[transcribe]"

EXPOSE 8000

CMD ["uvicorn", "services.orchestrator.api:app", "--host", "0.0.0.0", "--port", "8000"]
