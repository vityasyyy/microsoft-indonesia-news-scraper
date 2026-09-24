#!/usr/bin/env bash
set -euo pipefail
test -d corpus || { echo "missing corpus/: run \`make corpus\` first"; exit 1; }
zip -qr "corpus-articles-2025.zip" corpus
echo "wrote corpus-articles-2025.zip"
