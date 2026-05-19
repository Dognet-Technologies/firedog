#!/bin/bash
#
# Build helper for firedog-package: rebuilds the dog-agent static binary
# from the sibling dog_agent repo and stages it under dog-agent/dog-agent.
#
# The binary itself is gitignored — re-run this script before packaging.
#
# Usage:  ./build-package.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_REPO="${SCRIPT_DIR}/../../dog_agent"
TARGET=x86_64-unknown-linux-musl
BIN="${AGENT_REPO}/target/${TARGET}/release/dog-agent"

[[ -d "${AGENT_REPO}" ]] || { echo "dog_agent repo not found at ${AGENT_REPO}"; exit 1; }
command -v musl-gcc &>/dev/null || { echo "musl-gcc missing — install musl-tools"; exit 1; }

echo "==> cargo build --release --target ${TARGET}"
(cd "${AGENT_REPO}" && cargo build --release --target "${TARGET}")

[[ -x "${BIN}" ]] || { echo "build produced no binary at ${BIN}"; exit 1; }

install -m 0755 "${BIN}"                                  "${SCRIPT_DIR}/dog-agent/dog-agent"
install -m 0644 "${AGENT_REPO}/debian/dog-agent.service"  "${SCRIPT_DIR}/dog-agent/dog-agent.service"
install -m 0644 "${AGENT_REPO}/config.example.toml"       "${SCRIPT_DIR}/dog-agent/agent.conf.example"

echo "==> $(file "${SCRIPT_DIR}/dog-agent/dog-agent" | cut -d: -f2-)"
echo "==> package ready: $(du -sh "${SCRIPT_DIR}" | cut -f1)"
