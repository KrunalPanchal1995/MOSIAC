#!/usr/bin/env bash
# Resume the autonomous CFDCore.jl session after a plan-limit refresh or
# interruption. See RESUME.md for full context; this script just re-invokes
# Claude Code with an instruction to read the handoff docs and continue.
#
# NOTE (documented limitation — see the assistant's message to the user):
# this script cannot itself authenticate as the user or know precisely when
# a plan limit resets. It is meant to be run manually by the user when they
# return, or wired into their own cron/scheduler with the correct timing —
# it does not self-schedule.
#
# Usage:
#   ./resume.sh                 # interactive
#   ./resume.sh --headless      # non-interactive (claude -p), logs to resume.log
echo "Waiting 300 minutes before resuming..."
sleep 300m
echo "Starting at $(date)"
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

#PROMPT="Read memory files and code_review.md. See what is remaining in implementing the suggestions in code_review.md. Implement those. under ~/.claude/projects/-data-OPENFOAM-WRAPPER/memory/. Continue executing prompt.txt from the current work package noted in RESUME.md — do not restart completed work packages."
PROMPT="Read prompt.txt, and execute where you left"
if [[ "${1:-}" == "--headless" ]]; then
  echo "[$(date -Iseconds)] resuming (headless)" >> resume.log
  CLAUDE_CONFIG_DIR=~/.claude-work claude --enable-auto-mode -p "$PROMPT" --allowedTools "Bash,Read,Edit,Write" >> resume.log 2>&1
else
  echo "Resuming CFDCore.jl autonomous session. Paste this if not auto-filled:"
  echo
  echo "$PROMPT"
  echo
  CLAUDE_CONFIG_DIR=~/.claude-work claude --enable-auto-mode --continue "$PROMPT" --allowedTools "Bash,Read,Edit,Write" || \
  CLAUDE_CONFIG_DIR=~/.claude-work claude --enable-auto-mode "$PROMPT" --allowedTools "Bash,Read,Edit,Write"
fi
