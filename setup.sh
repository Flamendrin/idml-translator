#!/bin/bash

echo "📦 Instalace závislostí..."
sudo apt update
sudo apt install python3-pip python3-venv -y

echo "🧪 Vytvářím virtuální prostředí..."
python3 -m venv venv
source venv/bin/activate

echo "📦 Instaluji Python balíčky..."
pip install --upgrade pip
pip install flask lxml openai python-dotenv

echo "✅ Hotovo. Spusťte ./start.sh pro spuštění aplikace."
