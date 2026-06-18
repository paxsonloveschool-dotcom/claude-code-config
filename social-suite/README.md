# Social Suite

An in-house, automated social-media content pipeline. Drop a raw long-form video
into Dropbox and the suite clips it into vertical shorts, transcribes and burns in
animated captions, writes hooks/captions/hashtags with Claude, and schedules the
posts across platforms — all driven by an orchestrator.

```
Dropbox (raw video)
      │  ingest: watch + download
      ▼
auto-clip → 9:16 vertical shorts          (clip)
      ▼
transcribe → word-level segments          (caption/transcribe)
      ▼
burn animated captions/text              (caption/burn)
      ▼
AI hooks / captions / hashtags (Claude)   (write)
      ▼
schedule / post via social engine        (publish → Postiz)
      ▲
      └── orchestrator runs the whole chain automatically
```

## Status

This is a **skeleton**: clean module boundaries and typed interfaces with
`NotImplementedError`/mock stubs. Nothing here calls a real external service yet —
every component is a documented seam where a real implementation drops in. The
FastAPI app boots and every module imports without heavy dependencies installed.

## Architecture

Each pipeline stage is its own package under `services/` with a narrow public
surface, so a real implementation can replace a stub without touching the rest:

| Stage | Package | Entry point | Fills in with |
|-------|---------|-------------|---------------|
| Ingest | `services/ingest` | `dropbox_client.list_new_files()` / `download()` | Dropbox SDK |
| Clip | `services/clip` | `clipper.clip(video_path)` | ClipsAI / ShortGPT |
| Transcribe | `services/caption` | `transcribe.transcribe(video)` | faster-whisper / WhisperX |
| Burn captions | `services/caption` | `burn.burn_captions(video, segments)` | ffmpeg + libass (ASS) |
| Write | `services/write` | `copywriter.generate_caption(context)` | Anthropic SDK (`claude-opus-4-8`) |
| Publish | `services/publish` | `poster.schedule_post(...)` | Postiz public API |
| Orchestrate | `services/orchestrator` | `pipeline.run_pipeline()` + `api.py` | glue / scheduling |

The shared data shapes (`Clip`, `Segment`, `GeneratedCopy`, `ScheduledPost`) live
next to the stubs that produce them and are documented in `ARCHITECTURE.md`.

## How to run

```bash
# 1. (optional) create a virtualenv
python -m venv .venv && source .venv/bin/activate

# 2. install (real deps are pinned loosely in pyproject.toml)
pip install -e .

# 3. configure
cp .env.example .env   # then fill in credentials

# 4. start the orchestrator API
uvicorn services.orchestrator.api:app --reload
#   GET  /health   -> {"status": "ok"}
#   POST /run      -> triggers run_pipeline() (returns mock result for now)
```

Or with Docker:

```bash
docker compose up
```

### Parse check (no heavy deps required)

```bash
python -m compileall social-suite/services
python -c "import services.orchestrator.api"   # from inside social-suite/
```

## Fill these in next (roadmap)

1. **Ingest** — wire `dropbox_client.py` to the Dropbox SDK; implement
   `list_new_files()` (cursor-based delta) and `download()`.
2. **Clip** — drop ClipsAI/ShortGPT into `clipper.py`; produce 9:16 `Clip` objects
   with start/end + virality scoring.
3. **Transcribe** — implement `transcribe.py` with faster-whisper/WhisperX for
   word-level timestamps.
4. **Burn** — implement `burn.py`: render segments to an ASS subtitle file and
   burn with ffmpeg/libass (animated/karaoke styling).
5. **Write** — implement `copywriter.py` against the Anthropic SDK
   (`claude-opus-4-8`, adaptive thinking). Return hook + caption + hashtags.
6. **Publish** — implement `poster.py` against Postiz `POST /public/v1/posts`.
7. **Orchestrator** — flesh out `pipeline.run_pipeline()` to chain the stages,
   add a queue (Redis) + worker, and a scheduler/trigger.

See `ARCHITECTURE.md` for the data flow, each component's role, and the
connection checklist.
