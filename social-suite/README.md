# Social Suite

A pipeline of small, independently-deployable services that turn raw media into
captioned, scheduled social posts. Each service lives in its own folder under
`services/` and is owned by one work session at a time so parallel sessions
never collide.

```
audio/video ─▶ transcription ─▶ caption/burn-in ─▶ publisher (Postiz) ─▶ platforms
                    │                                     ▲
                    └── caption-gen (post copy) ──────────┘
```

## Services & ownership

| Service                  | Folder                       | Status      | Owner / branch                  |
|--------------------------|------------------------------|-------------|---------------------------------|
| Transcription / ASR      | `services/transcription`     | scaffolded  | `claude/clever-wozniak-fhv80z`  |
| Caption / burn-in        | `services/caption-burn-in`   | in progress | `claude/social-suite`           |
| Caption copy generation  | `services/caption-gen`       | planned     | —                               |
| Publisher (Postiz)       | `services/publisher`         | planned     | wraps existing `postiz/`        |
| Orchestrator / pipeline  | `services/orchestrator`      | planned     | —                               |

## Conventions

- One service = one folder under `services/<name>`. Don't edit another session's
  folder; coordinate via this table + the per-service README contract.
- Each service is a Cloudflare Worker (TypeScript) unless noted, mirroring
  `tools/social-ai-responder`.
- Services talk over **stable HTTP contracts** documented in their own README.
  The transcription contract (the input to caption/burn-in) is in
  `services/transcription/README.md`.

## Service contracts (the seams)

- **transcription → caption/burn-in:** transcription emits timed cues as SRT,
  VTT, and a JSON `segments[]`/`words[]` shape. caption/burn-in consumes those
  cues to render on-screen captions. See `services/transcription/README.md`.
