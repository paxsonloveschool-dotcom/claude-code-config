# Transcription Service

ASR for the social suite. Audio/video in → **timed transcript out** (SRT / VTT /
JSON). Runs on Cloudflare Workers using **Workers AI Whisper** (free daily
allowance, no extra account). This is the upstream of the caption/burn-in
service: it produces the timed cues that get burned onto video.

```
audio/video ─▶ [transcription] ─▶ SRT / VTT / JSON cues ─▶ [caption/burn-in] ─▶ video
```

## Endpoints

| Method | Path          | Purpose                                  |
|--------|---------------|------------------------------------------|
| GET    | `/`           | Health check (`transcription: ok`)       |
| POST   | `/transcribe` | Transcribe audio → timed transcript      |

### `POST /transcribe`

Send the audio in **any one** of these forms:

- `multipart/form-data` with a `file` field
- JSON `{ "url": "https://.../clip.mp3" }` — the worker fetches it
- raw audio bytes as the request body (`Content-Type: audio/*` or `video/*`)

Query params:

| Param    | Default | Meaning                                              |
|----------|---------|------------------------------------------------------|
| `key`    | —       | Auth; must equal `AUTH_KEY` (or send `x-auth-key`)   |
| `format` | `json`  | `json` \| `srt` \| `vtt`                             |
| `lang`   | auto    | Optional language hint passed to Whisper             |

#### Examples

```bash
# Multipart file upload, full JSON result
curl -X POST "https://transcription.<you>.workers.dev/transcribe?key=$AUTH_KEY" \
  -F file=@clip.mp4

# Transcribe a remote URL, get an .srt back
curl -X POST "https://transcription.<you>.workers.dev/transcribe?key=$AUTH_KEY&format=srt" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/clip.mp3"}'

# Raw bytes
curl -X POST "https://transcription.<you>.workers.dev/transcribe?key=$AUTH_KEY&format=vtt" \
  -H 'Content-Type: audio/mpeg' --data-binary @clip.mp3
```

## Response contract (`format=json`)

This is the **stable shape** downstream services consume — additive changes only.

```jsonc
{
  "text": "full plain-text transcript",
  "language": "en",            // when reported
  "duration": 12.84,           // seconds, when reported
  "segments": [                // caption-ready cues
    { "start": 0.0, "end": 2.1, "text": "Hey, welcome back.",
      "words": [ { "word": "Hey,", "start": 0.0, "end": 0.4 } ] }
  ],
  "words": [                   // word-level timing (empty if model gives none)
    { "word": "Hey,", "start": 0.0, "end": 0.4 }
  ],
  "srt": "1\n00:00:00,000 --> 00:00:02,100\nHey, welcome back.\n",
  "vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:02.100\nHey, welcome back.\n"
}
```

`segments` are shaped for legibility: when word timing is available they're
re-chunked to stay under `MAX_CUE_CHARS` chars and `MAX_CUE_SECONDS` seconds,
breaking on sentence punctuation where possible.

Errors are `{ "error": "..." }` with a `4xx`/`5xx` status.

## Config (`wrangler.toml [vars]`)

| Var               | Default                            | Meaning                          |
|-------------------|------------------------------------|----------------------------------|
| `WHISPER_MODEL`   | `@cf/openai/whisper-large-v3-turbo`| ASR model id                     |
| `MAX_CUE_CHARS`   | `42`                               | Max chars per re-chunked cue     |
| `MAX_CUE_SECONDS` | `6`                                | Max seconds per re-chunked cue   |
| `MAX_AUDIO_BYTES` | `26214400` (25 MiB)                | Reject larger payloads up front  |

Secret (not in `vars`): `AUTH_KEY` gates `POST /transcribe`.

## Develop & deploy

```bash
npm install
cp .dev.vars.example .dev.vars   # set AUTH_KEY for local auth (optional in dev)
npm run dev                       # wrangler dev
npm run typecheck                 # tsc --noEmit

npm run secret:authkey            # set AUTH_KEY in production
npm run deploy                    # wrangler deploy
```

## Notes & limits

- **No `AUTH_KEY` = open endpoint.** Fine locally; always set it before deploying.
- Whisper and the Worker request body both cap payload size — keep clips short
  (a minute or two of speech). For longer media, segment upstream and stitch the
  cue offsets. `MAX_AUDIO_BYTES` rejects oversized input with a clear `413`.
- The base `@cf/openai/whisper` model returns word timing but not always
  segments; turbo returns both. The normalizer handles either and falls back to
  a single untimed cue if a model returns text only.
