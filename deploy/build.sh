#!/usr/bin/env bash
# Run by deployd on rpi5 before rsyncing to rpi3 (cwd = repo root).
#
# Deliberately does NOT run `npm run build`: the React source for the Draft
# Desk and sign-in UI (shipped 2026-08-08) was lost, and frontend/dist is the
# only surviving copy of the live bundle (now committed). Rebuilding from
# frontend/src would ship a bundle without those features. Restore the full
# build here once the frontend source is reconstructed.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p backend/staticfiles backend/templates
rm -rf backend/staticfiles/*
cp -r frontend/dist/* backend/staticfiles/
cp backend/staticfiles/index.html backend/templates/index.html
