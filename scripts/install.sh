#!/usr/bin/env bash
# PrivateMind installer — clone (if needed), pip install, init data dir (slow_start).
# Review before running: curl -fsSL …/install.sh | bash
set -euo pipefail

REPO="${PRIVATE_MIND_INSTALL_REPO:-https://github.com/GeneralKnowledge/PrivateMind.git}"
BRANCH="${PRIVATE_MIND_INSTALL_BRANCH:-main}"
INSTALL_DIR="${PRIVATE_MIND_INSTALL_DIR:-${HOME}/PrivateMind}"
WITH_DEV="${PRIVATE_MIND_INSTALL_DEV:-1}"

usage() {
  cat <<'EOF'
PrivateMind install script

Usage:
  curl -fsSL https://raw.githubusercontent.com/GeneralKnowledge/PrivateMind/main/scripts/install.sh | bash

  ./scripts/install.sh [--dir PATH] [--branch NAME] [--no-dev]

Environment:
  PRIVATE_MIND_INSTALL_REPO   Git remote (default: GeneralKnowledge/PrivateMind)
  PRIVATE_MIND_INSTALL_BRANCH Branch to clone (default: main)
  PRIVATE_MIND_INSTALL_DIR    Clone target (default: ~/PrivateMind)
  PRIVATE_MIND_REPO_ROOT      Skip clone; install from existing checkout
  PRIVATE_MIND_INSTALL_DEV    1 = pip install -e ".[dev]" (default), 0 = runtime only

After install: docs/FIRST_BOOT_ADMIN.md — vault, accounts, wake.
EOF
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: missing required command: $1" >&2
    exit 1
  fi
}

check_python() {
  need_cmd python3
  if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "error: Python 3.11+ required" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help) usage; exit 0 ;;
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --no-dev)
      WITH_DEV=0
      shift
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

need_cmd git
check_python

if [[ -n "${PRIVATE_MIND_REPO_ROOT:-}" ]] && [[ -f "${PRIVATE_MIND_REPO_ROOT}/pyproject.toml" ]]; then
  cd "${PRIVATE_MIND_REPO_ROOT}"
elif [[ -f "pyproject.toml" ]] && grep -q 'name = "privatemind"' pyproject.toml 2>/dev/null; then
  :
else
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo "==> Using existing clone: ${INSTALL_DIR}"
    cd "${INSTALL_DIR}"
    git fetch origin "${BRANCH}" --depth 1 2>/dev/null || git fetch origin
    git checkout "${BRANCH}" 2>/dev/null || git checkout main
    git pull --ff-only origin "${BRANCH}" 2>/dev/null || true
  else
    echo "==> Cloning ${REPO} (branch ${BRANCH}) -> ${INSTALL_DIR}"
    git clone --depth 1 --branch "${BRANCH}" "${REPO}" "${INSTALL_DIR}"
    cd "${INSTALL_DIR}"
  fi
fi

echo "==> Installing Python package from $(pwd)"
python3 -m pip install -U pip wheel
if [[ "${WITH_DEV}" == "1" ]]; then
  python3 -m pip install -e ".[dev]"
else
  python3 -m pip install -e .
fi

echo "==> Initializing PrivateMind data directory (~/.privatemind)"
privatemind init
privatemind mode status || true

cat <<EOF

Install complete.

Next (human — vault passphrase never goes in this script):
  export PRIVATE_MIND_VAULT_PASSPHRASE='…'
  privatemind vault init --passphrase "\$PRIVATE_MIND_VAULT_PASSPHRASE"
  # See docs/FIRST_BOOT_ADMIN.md for accounts, node init, wake

Docs: ${PWD}/docs/FIRST_BOOT_ADMIN.md
EOF
