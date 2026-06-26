# Headroom agent hooks

This plugin exposes lightweight startup hooks for Claude Code and GitHub Copilot CLI.

The hooks call:

```bash
headroom init hook ensure
```

That hidden helper checks for a matching durable `headroom init` deployment and starts it if needed.

> Vendored from https://github.com/headroomlabs-ai/headroom (`plugins/headroom-agent-hooks`, v0.22.3)
> because the agent egress proxy blocks `git clone github.com`. The hooks are inert without the
> `headroom` binary on PATH — install it separately (see the upstream repo).
