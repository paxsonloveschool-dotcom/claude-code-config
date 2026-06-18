# Architecture

## Data flow

```
┌────────────┐   list_new_files()/download()   ┌────────────┐
│  Dropbox   │ ──────────────────────────────▶ │   ingest   │
└────────────┘                                  └─────┬──────┘
                                                      │ local raw video path (str)
                                                      ▼
                                               ┌────────────┐
                                               │    clip    │  clip(video_path) -> list[Clip]
                                               └─────┬──────┘
                                                      │ Clip (9:16 vertical short)
                                                      ▼
                                          ┌───────────────────────┐
                                          │ caption.transcribe    │  transcribe(video) -> list[Segment]
                                          └─────────┬─────────────┘
                                                    │ list[Segment] (word-level)
                                                    ▼
                                          ┌───────────────────────┐
                                          │ caption.burn          │  burn_captions(video, segments) -> str
                                          └─────────┬─────────────┘
                                                    │ captioned video path (str)
                                                    ▼
                                               ┌────────────┐
                                               │   write    │  generate_caption(context) -> GeneratedCopy
                                               └─────┬──────┘
                                                      │ GeneratedCopy (hook/caption/hashtags)
                                                      ▼
                                               ┌────────────┐
                                               │  publish   │  schedule_post(...) -> ScheduledPost
                                               └─────┬──────┘
                                                      │ POST /public/v1/posts
                                                      ▼
                                               ┌────────────┐
                                               │  Postiz    │ → TikTok / IG Reels / YT Shorts / ...
                                               └────────────┘

         orchestrator.pipeline.run_pipeline()  ── drives every arrow above
         orchestrator.api  ── /health, POST /run trigger the orchestrator
```

## Component roles

| Component | Role | Input → Output |
|-----------|------|----------------|
| `services/ingest/dropbox_client.py` | Watch a Dropbox folder for new raw uploads and pull them to local disk. | Dropbox folder → local file path(s) |
| `services/clip/clipper.py` | Cut a long video into multiple 9:16 vertical shorts, each a self-contained moment. | video path → `list[Clip]` |
| `services/caption/transcribe.py` | Produce word-level transcript segments with timestamps. | video → `list[Segment]` |
| `services/caption/burn.py` | Render the segments as animated captions and burn them into the video. | video + segments → captioned video path |
| `services/write/copywriter.py` | Generate a scroll-stopping hook, a platform caption, and hashtags from clip context. | context → `GeneratedCopy` |
| `services/publish/poster.py` | Schedule/post the finished clip + copy to social channels. | clip + copy + channels + time → `ScheduledPost` |
| `services/orchestrator/pipeline.py` | Chain ingest → clip → caption → write → publish. | trigger → run summary |
| `services/orchestrator/api.py` | HTTP surface (`/health`, `POST /run`) to trigger and monitor the orchestrator. | HTTP → orchestrator calls |

## Shared data shapes

Defined alongside the stub that produces them (kept as plain dataclasses so the
skeleton has zero third-party model deps):

- **`Clip`** (`services/clip/clipper.py`) — one vertical short: source path, output
  path, start/end seconds, aspect ratio, optional virality score + title.
- **`Segment`** (`services/caption/transcribe.py`) — a transcript unit: text,
  start/end seconds, and optional word-level timings for karaoke-style animation.
- **`GeneratedCopy`** (`services/write/copywriter.py`) — `hook`, `caption`,
  `hashtags`, plus the model id used.
- **`ScheduledPost`** (`services/publish/poster.py`) — Postiz post id, channels,
  scheduled time, and status.

## Where harvested OSS plugs in

| Seam | Project to harvest | Notes |
|------|--------------------|-------|
| `ingest/dropbox_client.py` | **Dropbox SDK** (`dropbox`) | Use `files_list_folder` + cursor for delta polling; `files_download_to_file`. |
| `clip/clipper.py` | **ClipsAI** / **ShortGPT** | ClipsAI for transcript-driven clip detection + 9:16 reframing; ShortGPT for the pipeline patterns. |
| `caption/transcribe.py` | **faster-whisper** / **WhisperX** | WhisperX gives accurate word-level alignment; faster-whisper is the fast CTranslate2 backend. |
| `caption/burn.py` | **ffmpeg + libass** | Emit an `.ass` file with karaoke (`\k`) timing; burn via `ffmpeg -vf "ass=subs.ass"`. |
| `write/copywriter.py` | **Anthropic SDK** | `anthropic` Python SDK, model `claude-opus-4-8`, adaptive thinking. |
| `publish/poster.py` | **Postiz public API** | `POST /public/v1/posts`; auth via API key header. |

## Connection checklist

Wire these up as you replace each stub (credentials documented in `.env.example`):

- [ ] **Dropbox** — app created, `DROPBOX_ACCESS_TOKEN` (or refresh-token flow) set, watch folder `DROPBOX_WATCH_FOLDER` exists.
- [ ] **Clip engine** — ClipsAI/ShortGPT installed; ffmpeg on PATH for reframing.
- [ ] **Whisper** — model weights downloaded; GPU optional. `WHISPER_MODEL` / `WHISPER_DEVICE` set.
- [ ] **ffmpeg/libass** — `ffmpeg` built with `--enable-libass`; caption style/font configured.
- [ ] **Anthropic** — `ANTHROPIC_API_KEY` set; model `claude-opus-4-8` reachable.
- [ ] **Postiz** — instance reachable at `POSTIZ_API_URL`; `POSTIZ_API_KEY` valid; channels connected per `POSTIZ_DEFAULT_CHANNELS`.
- [ ] **Per-platform creds** — only needed if posting direct (not via Postiz); see `.env.example`.
- [ ] **Queue** — Redis reachable at `REDIS_URL`; worker running.
- [ ] **Orchestrator** — FastAPI app boots; `/health` returns ok; `POST /run` triggers the chain.
