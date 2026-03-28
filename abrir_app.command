#!/bin/bash
DIR="/Users/mauroramos/Documents/Proyectos ClaudeCode/Software Apuestas de valor"
cd "$DIR"

echo "Instalando dependencias..."
python3 -m pip install -r "$DIR/requirements.txt" -q 2>/dev/null

echo "Iniciando app en http://127.0.0.1:8080"
(sleep 4 && open http://127.0.0.1:8080) &

python3 "$DIR/app.py"
