#!/usr/bin/env bash
# Run by deployd on rpi5 before rsyncing to rpi3 (cwd = repo root).
#
# Builds the React frontend from frontend/src (the Draft Desk / sign-in
# source was recovered from the Mac checkout on 2026-09-04 and is tracked
# again) and stages it where Django serves it: backend/staticfiles (rsynced
# to rpi3; STATIC_ROOT) plus the SPA shell in backend/templates.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend ci --no-audit --no-fund
fi
npm --prefix frontend run build

mkdir -p backend/staticfiles backend/templates
rm -rf backend/staticfiles/*
cp -r frontend/dist/* backend/staticfiles/
cp backend/staticfiles/index.html backend/templates/index.html
