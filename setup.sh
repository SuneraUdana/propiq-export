#!/usr/bin/env bash
# PropIQ — One-command local setup
set -e
echo "🏠 PropIQ Setup"
echo "────────────────────────────────"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
python -m spacy download en_core_web_sm --quiet 2>/dev/null || true
cp .env.example .env
mkdir -p data reports output assets
echo "────────────────────────────────"
echo "✅ Setup complete!"
echo ""
echo "Run the pipeline:"
echo "  source .venv/bin/activate"
echo "  python -m propiq.main"
echo ""
echo "Run the chatbot server:"
echo "  python -m propiq.server"
echo "  → http://localhost:8000"
