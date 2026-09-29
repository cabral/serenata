#!/bin/bash
# Sign assistant commits as the maintainer in cloud sessions (ADR-0009).
#
# Runs only in Claude Code on the web, and only when the clone is the
# maintainer's own repository, so a fork or someone else's session is never
# signed as the maintainer. Local git config only; nothing global is touched.
set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}"
case "$(git remote get-url origin 2>/dev/null || true)" in
*cabral/serenata | *cabral/serenata.git) ;;
*) exit 0 ;;
esac

git config user.name "Felipe Benites Cabral"
git config user.email "felipe.benites@gmail.com"
git config core.hooksPath .githooks
