#!/usr/bin/env bash
# Run a CI step; on failure surface the last lines of output as a GitHub annotation.
# usage: scripts/ci_run.sh "<title>" command args...
title="$1"; shift
log="$(mktemp)"
"$@" 2>&1 | tee "$log"
code=${PIPESTATUS[0]}
if [ "$code" -ne 0 ]; then
  msg="$(grep -v '^\s*$' "$log" | tail -n 45 | cut -c1-220 | sed 's/%/%25/g;s/\r//g' | awk 'BEGIN{ORS="%0A"}{print}')"
  echo "::error title=${title}::${msg}"
fi
exit "$code"
