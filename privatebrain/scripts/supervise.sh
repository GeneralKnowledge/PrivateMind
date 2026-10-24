#!/usr/bin/env bash
# A minimal external supervisor for `privatebrain run`: the brain does not guarantee its own
# survival. Every CHECK seconds it asks `privatebrain health`:
#   exit 0  healthy (or inside a model call that is still within its time limit): nothing to do
#   exit 1  the loop holds its lock but its heartbeat is stale (hung, or stopped): SIGKILL it, restart
#   exit 2  not running: start it
# On restart the loop recovers by itself (see SUBSTRATE.md, "Recovery"). For production use
# systemd or launchd instead; SUBSTRATE.md has a unit file that does the same thing.
#
#   scripts/supervise.sh <brain-home> [check-seconds] [extra `run` args...]
set -uo pipefail
H="${1:?usage: supervise.sh <brain-home> [check-seconds] [run args...]}"
CHECK="${2:-10}"
shift $(( $# >= 2 ? 2 : 1 ))
PB=(python -m privatebrain.cli --home "$H")
log() { printf '%s supervise: %s\n' "$(date -u +%FT%TZ)" "$*" >>"$H/supervise.log"; }
start() { "${PB[@]}" run "$@" >>"$H/loop.log" 2>&1 & log "started loop pid $!"; }
trap 'log "supervisor exiting"; exit 0' TERM INT
while true; do
  out=$("${PB[@]}" health 2>/dev/null); code=$?
  case $code in
    0) ;;
    1) pid=$(printf '%s' "$out" | python -c 'import json,sys; print(json.load(sys.stdin).get("pid") or "")')
       log "stalled ($out); killing pid $pid"
       [ -n "$pid" ] && kill -KILL "$pid" 2>/dev/null
       sleep 1; start "$@" ;;
    *) log "not running ($out)"; start "$@" ;;
  esac
  sleep "$CHECK"
done
