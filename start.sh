#!/bin/bash

echo "🔄 Aktivuji virtuální prostředí..."
source venv/bin/activate

echo "✅ Načítám .env..."
export $(grep -v '^#' .env | xargs)

echo "🚀 Spouštím aplikaci..."
python app.py
