# Quickstart — Run the Social Suite

How to run the in-house pipeline once your keys are ready. Until then, you can
run the **dry-run** (no keys, no external calls) to watch the whole flow work.

## 0. Prerequisites
- Python 3.11+
- `ffmpeg` installed (`brew install ffmpeg` on Mac) — for clipping + caption burn
- A running **Postiz** instance with connected channels (the posting engine)
- Keys: Dropbox app creds, `ANTHROPIC_API_KEY`, Postiz API key

## 1. Install
```bash
cd social-suite
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # core (fastapi, etc.)
pip install -e ".[media,ai,cloud]"   # heavy extras: whisper, anthropic, dropbox
```

## 2. Configure
```bash
cp .env.example .env
# Fill in: DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN, ANTHROPIC_API_KEY,
#          POSTIZ_API_URL/POSTIZ_API_KEY, POSTIZ_DEFAULT_CHANNELS, etc.
```

## 3. Try it with NO keys first (dry-run)
Proves the full chain works end-to-end using in-memory fakes:
```bash
python3 -c "from services.orchestrator.pipeline import run_pipeline; \
import json; print(json.dumps(run_pipeline(dry_run=True), indent=2, default=str))"
```
Expected: a summary with counts for files → clips → captioned → written → scheduled.

## 4. Run the orchestrator API
```bash
uvicorn services.orchestrator.api:app --reload --port 8000
# GET  http://localhost:8000/health   -> {"status":"ok"}
# POST http://localhost:8000/run      -> runs the pipeline
```

## 5. Go live (real run)
Once `.env` has real keys and Postiz has connected channels:
```bash
python3 -c "from services.orchestrator.pipeline import run_pipeline; \
print(run_pipeline(dry_run=False))"
```
This will: pull new videos from your Dropbox folder → auto-clip to 9:16 →
transcribe → burn animated captions → Claude writes the copy → schedule the
posts in Postiz.

## 6. Automate it (continuous)
Run the orchestrator as a background worker that watches Dropbox (longpoll) and
processes new uploads automatically. See `services/ingest/dropbox_client.py`
(`longpoll`) and wire it to a loop / RQ worker per `RESEARCH.md` §7.

## Pipeline at a glance
```
Dropbox → clip (9:16 highlights) → transcribe → burn captions → Claude copy → Postiz post
```

## Tuning (env vars)
| Var | Effect |
|---|---|
| `CLIP_MAX_SECONDS` / `CLIP_MIN_SECONDS` | clip length bounds |
| `CLIP_USE_LLM=1` | use Claude to re-rank highlights (default: offline heuristic) |
| `WHISPER_MODEL` / `WHISPER_DEVICE` | transcription model / cpu|cuda |
| `CAPTION_FONT` / `CAPTION_FONT_SIZE` | caption styling |
| `POSTIZ_DEFAULT_CHANNELS` | comma-separated channel IDs to post to |

See `RESEARCH.md` for component sources/licenses and `ARCHITECTURE.md` for the
full design.
