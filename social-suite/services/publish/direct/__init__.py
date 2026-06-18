"""Direct platform posting (no Postiz) — fire straight at the platform APIs.

Used by the GitHub Actions cron runner so posting needs no always-on server and
no self-hosted Postiz. Currently covers Meta (Facebook + Instagram) via the
Graph API. Each poster lazy-imports ``urllib`` so this package imports cleanly
with no third-party deps and no network at import time.
"""

from .meta import post_facebook, post_instagram

__all__ = ["post_facebook", "post_instagram"]
