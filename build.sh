#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Running database initialization..."
python init_db.py

echo "Build completed successfully!"
