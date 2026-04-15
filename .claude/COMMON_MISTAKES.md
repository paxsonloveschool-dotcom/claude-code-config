# Common Mistakes (Add bugs that took >1hr to debug)

1. **GitHub auth scope**: Tokens need `repo` scope for push/create. No-scope tokens silently fail.
2. **Windows path separators**: Use forward slashes in bash, backslashes in PowerShell. Mix causes silent failures.
3. **gh CLI not in PATH**: After install, must `export PATH="/c/Program Files/GitHub CLI:$PATH"` in each bash session.
4. **SSH keys missing**: This machine has no SSH keys. Use HTTPS + token auth for git operations.
5. **Browser auth timeout**: `gh auth login --web` times out in ~2min. Use `--with-token` instead.
6. **RTK hook mode needs WSL**: `rtk init -g` on native Windows silently falls back to legacy mode and injects ~140 lines into CLAUDE.md. Install WSL first, then run RTK.
7. **RTK uninstall is broken on Windows**: `rtk init -g --uninstall` says "nothing to remove" even when the legacy block exists. Delete the `<!-- rtk-instructions v2 -->` block manually.
