# Build-Ready Research — In-House Social Content Suite

Verified component choices for the pipeline. Every component is open-source and
either permissively licensed (vendor directly) or AGPL (run as an isolated
service behind its API). See **License Strategy** for the boundary that keeps
our orchestrator code obligation-free.

**Chosen stack (one line):** AI-Youtube-Shorts-Generator (clip) → faster-whisper
/ WhisperX (transcribe) → ASS + ffmpeg/libass (animated captions) → Anthropic
SDK `claude-opus-4-8` (copy) → Postiz public API (post) → RQ + Redis/Valkey +
Dropbox watcher (orchestrate).

## Component decisions

| Stage | PRIMARY (harvest) | License | Backup / notes |
|---|---|---|---|
| **Clip → 9:16** | [samuraigpt/ai-youtube-shorts-generator](https://github.com/samuraigpt/ai-youtube-shorts-generator) | **MIT** ✅ | Does all 4: LLM virality scoring, 9:16 reframe, OpenCV face-tracking, faster-whisper transcript cuts. Vendor directly. |
| | [FujiwaraChoki/supoclip](https://github.com/FujiwaraChoki/supoclip) ("supoclip" — the one you named) | AGPL ⚠️ | Closest OpusClip clone (FastAPI+ARQ+Postgres+Redis), but AGPL + needs paid AssemblyAI. Use only as isolated service/reference. |
| | [ClipsAI/clipsai](https://github.com/ClipsAI/clipsai) | MIT ✅ | Stale; great speaker-follow reframe (WhisperX+pyannote) — code reference only. |
| **Transcribe** | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CPU) | MIT ✅ | `word_timestamps=True`, int8. |
| | [m-bain/whisperX](https://github.com/m-bain/whisperX) (GPU) | BSD-2 ✅ | wav2vec2 forced alignment = tightest word timing for animation. |
| **Animated captions** | ffmpeg + [libass](https://github.com/libass/libass) (our `ass_builder.py`) | libass ISC ✅ / ffmpeg GPL caveat | Generate ASS karaoke `\kf` per word → `ffmpeg -vf ass`. Shell out to ffmpeg (don't link) to avoid GPL. |
| | [unconv/captacity](https://github.com/unconv/captacity) | MIT ✅ | Reference impl only. |
| **AI copy** | [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python), model `claude-opus-4-8` | — | Paid usage. Prompt-cache brand prompt; Batches API (−50%) for bulk; `claude-haiku-4-5` for hashtags. |
| **Post to all 6** | [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) | AGPL ⚠️ | Call its **public API** over the network (no AGPL trigger). All 6 platforms native. |
| | [brightbeanxyz/brightbean-studio](https://github.com/brightbeanxyz/brightbean-studio) | AGPL ⚠️ | Backup; lighter Django, REST+MCP, all 6, no paywall. |
| | ~~Mixpost~~ | — | ❌ Free Lite can't reach IG/TikTok/YouTube/LinkedIn (paid). |
| **Ingest** | [dropbox/dropbox-sdk-python](https://github.com/dropbox/dropbox-sdk-python) (pin ≥12.0.2) | MIT ✅ | Refresh-token auth; `files_list_folder_longpoll` to watch a folder (no inbound port). |
| **Orchestrate** | [RQ](https://python-rq.org/) + [Valkey](https://valkey.io) | BSD ✅ | Durable jobs, per-job isolation, retries. Skip Celery/Temporal (overkill). |

## Postiz public API (the posting call)
- Base (self-hosted): `https://{BACKEND_URL}/public/v1`
- Auth header: `Authorization: <api-key>` (raw, **no** `Bearer`)
- `GET /public/v1/integrations` → channel IDs
- `POST /public/v1/posts` → one call posts to all 6: `type` (`now|schedule|draft`),
  `date`, and a `posts[]` array with one entry per channel (`integration.id` +
  `settings.__type` = `instagram|facebook|tiktok|youtube|x|linkedin`). Rate limit ~90/hr.
- ⚠️ Postiz **v2.12+ requires a Temporal stack** (~8 services, ~8 GB RAM). Keep it
  on its own host, pin pre-2.12, or use BrightBean if that weight is a problem.

## Connection / credentials checklist

| Connection | Credential | Free? | Approval needed? |
|---|---|---|---|
| Dropbox | app key + secret + offline refresh token (scopes: files.metadata.read, files.content.read) | ✅ | No (self-use) |
| Anthropic Claude | `ANTHROPIC_API_KEY` | ❌ usage ($5/$25 per 1M, opus 4.8) | No |
| Postiz | self-hosted API key (Settings → API Key) | ✅ | No (per-channel apps below) |
| Instagram / Facebook | Meta app + tokens (IG Professional + FB Page) | ✅ | ⚠️ **Meta App Review** |
| TikTok | TikTok for Developers app, Content Posting API | ✅ | ⚠️ **App audit** |
| YouTube | Google Cloud project, YouTube Data API v3 OAuth | ✅ (quota) | ⚠️ **OAuth verification** |
| X / Twitter | X Developer app + OAuth | ⚠️ free tier limited | Basic |
| LinkedIn | LinkedIn Developer app, Share/Marketing API | ✅ | ⚠️ **App review** |

**Long pole:** the platform app reviews (Meta/TikTok/YouTube/LinkedIn). Start these
applications NOW, in parallel with the build. Begin posting with the fastest to
approve (X, YouTube), add gated ones as reviews clear. Postiz maintains the
per-platform OAuth/integration so we don't reimplement it.

## License strategy (keeps our code obligation-free)
- **Vendor directly (MIT/BSD/Apache/ISC):** ai-youtube-shorts-generator,
  faster-whisper, whisperX, libass usage, Dropbox SDK, RQ, FastAPI, Anthropic SDK.
- **Isolate behind their HTTP API (AGPL):** Postiz, supoclip, BrightBean — run
  unmodified in their own containers; never `import` their source into ours.
  (AGPL only triggers if you modify the source and expose it over a network.)
- **ffmpeg GPL caveat:** a `--enable-gpl` build (libx264) is GPL — invoke ffmpeg
  as a **subprocess** (mere aggregation), never link it.
- **Avoid:** Remotion (paid at 4+ employees), Mixpost Pro, GPL-3 caption tools.
- **Redis 7.4+** is RSALv2/SSPL → use **Valkey** (BSD) for a clean license.

## Top risks → de-risk
1. **Platform API approvals** (highest) → apply now in parallel; start with X/YouTube.
2. **AGPL contamination** → hard boundary: AGPL only via HTTP API, own containers.
3. **Temporal weight (Postiz 2.12+)** → dedicated host / pin pre-2.12 / BrightBean.
4. **Compute** (face-track + WhisperX want GPU) → faster-whisper int8 on CPU; burst GPU if volume grows.
5. **Claude cost at scale** → prompt-cache brand prompt, Batches API (−50%), Haiku for hashtags.
