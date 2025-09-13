#!/bin/bash

echo "Building frontend for production..."
npm --prefix frontend run build

echo "Collecting frontend files for Django..."
rm -rf backend/static/*
cp -r frontend/dist/* backend/static/
cp backend/static/index.html backend/templates/index.html

echo "Build complete. Frontend files are ready for production."
