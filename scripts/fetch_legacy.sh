#!/usr/bin/env bash
set -euo pipefail
EXPECTED_SHA256="1a7bb86ae68043567f997fac08f32b891ecdbefc270d488ed2b0c2840c6f5bc5"
mkdir -p output/legacy
curl -fL --retry 3 \
  -o output/legacy/articles-2025-4.xlsx \
  https://github.com/vityasyyy/microsoft-indonesia-news-scraper/releases/download/articles-2025-4/articles-2025.xlsx
echo "$EXPECTED_SHA256  output/legacy/articles-2025-4.xlsx" | shasum -a 256 -c -
echo "wrote output/legacy/articles-2025-4.xlsx"
