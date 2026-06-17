#!/usr/bin/env bash
set -euo pipefail

echo "Atualizando pacotes..."
sudo apt update
sudo apt upgrade -y

echo "Instalando dependencias base..."
sudo apt install -y python3 python3-pip python3-venv git nginx

echo "Criando pasta do projeto..."
sudo mkdir -p /opt/agente-fundeb
sudo chown -R "$USER":"$USER" /opt/agente-fundeb

cat <<'EOF'
Proxima etapa:
1. Copie os arquivos do projeto para /opt/agente-fundeb
2. Entre na pasta do projeto
3. Crie o ambiente virtual
4. Instale as dependencias
5. Crie o arquivo .env manualmente
6. Configure o service do systemd
7. Configure o nginx
EOF
