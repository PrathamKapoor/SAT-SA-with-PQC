#!/bin/sh
# Start command for the Render demo service (see render.yaml).
#
# Render's `dockerCommand` does not appear to be handed to a real shell
# before it's exec'd: writing `sh -c '... "${PORT:-10000}"'` directly in
# render.yaml left $PORT completely unexpanded and the whole string was
# looked up as one literal (space-containing) command name, which fails
# with "not found". A committed script with a shebang sidesteps that,
# since the kernel itself invokes /bin/sh to run it, guaranteeing real
# shell parsing and parameter expansion.
#
# Demo state intentionally lives under /tmp so it resets safely on
# restart/redeploy (see render.yaml's comment on this service).
set -e
exec python scripts/serve_ui.py \
  --db /tmp/satsa-demo/satsa.db \
  --trust-key-dir /tmp/satsa-demo/keys \
  --host 0.0.0.0 \
  --port "${PORT:-10000}"
