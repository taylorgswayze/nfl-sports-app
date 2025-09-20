#!/bin/bash

echo "Building frontend for production..."
npm --prefix frontend run build

echo "Collecting frontend files for Django..."
rm -rf backend/staticfiles/*
cp -r frontend/dist/* backend/staticfiles/
cp backend/staticfiles/index.html backend/templates/index.html

echo "Build complete. Frontend files are ready for production."
