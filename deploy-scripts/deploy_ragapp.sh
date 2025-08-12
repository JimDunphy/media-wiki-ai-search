#!/usr/bin/env bash
#
# Author: GPT5
# Human: Jim Dunphy - Aug 12, 2025
#
# %%% NOT TESTED - do not run unless prepared to debug them
#

#
set -euo pipefail

APP_USER=ragapp
APP_GROUP=ragapp
APP_DIR=/opt/ragapp
VENV_DIR="$APP_DIR/.venv"
ENV_FILE=/etc/default/ragapp
APP_ENTRYPOINT=rag_app_v2.py
APP_HOST=127.0.0.1
APP_PORT=8501
BASE_URL_PATH=""   # set "rag" for subpath
SERVER_NAME=example.com

ensure_pkg() { sudo dnf -y install "$@"; }

create_user() {
  sudo useradd -r -M -s /sbin/nologin -U "$APP_USER" 2>/dev/null || true
  sudo mkdir -p "$APP_DIR" /var/log/ragapp
  sudo chown -R $APP_USER:$APP_GROUP "$APP_DIR" /var/log/ragapp
}

setup_python() {
  ensure_pkg python3 python3-pip python3-virtualenv
  sudo -u "$APP_USER" bash -lc "python3 -m venv '$VENV_DIR'"
  if [[ -f "$APP_DIR/requirements.txt" ]]; then
    sudo -u "$APP_USER" bash -lc "source '$VENV_DIR/bin/activate' && pip install --upgrade pip && pip install -r requirements.txt"
  else
    sudo -u "$APP_USER" bash -lc "source '$VENV_DIR/bin/activate' && pip install --upgrade pip && pip install streamlit"
  fi
}

write_env() {
  sudo bash -c "cat > '$ENV_FILE' <<EOF
OPENAI_API_KEY=REPLACE_ME
DB_PATH=$APP_DIR/data/lancedb
TABLE_NAME=wiki_aesir
HOST=$APP_HOST
PORT=$APP_PORT
BASE_URL_PATH=$BASE_URL_PATH
EOF"
  sudo chmod 600 "$ENV_FILE"
}

install_service() {
  sudo bash -c "cat > /etc/systemd/system/ragapp.service <<EOF
[Unit]
Description=RAG Streamlit App
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/streamlit run $APP_ENTRYPOINT \
  --server.address \${HOST} \
  --server.port \${PORT} \
  --server.headless true$( [[ -n "$BASE_URL_PATH" ]] && printf " \\\n  --server.baseUrlPath \${BASE_URL_PATH}" )
Restart=always
RestartSec=3
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=yes
ProtectSystem=full
StandardOutput=append:/var/log/ragapp/app.log
StandardError=append:/var/log/ragapp/app.err

[Install]
WantedBy=multi-user.target
EOF"
  sudo systemctl daemon-reload
  sudo systemctl enable --now ragapp
  sudo systemctl status ragapp --no-pager || true
}

install_nginx() {
  ensure_pkg nginx policycoreutils-python-utils firewalld
  sudo systemctl enable --now firewalld
  sudo firewall-cmd --add-service=http --add-service=https --permanent
  sudo firewall-cmd --reload

  if [[ -z "$BASE_URL_PATH" ]]; then
    sudo bash -c "cat > /etc/nginx/conf.d/ragapp.conf <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    location / {
        proxy_pass http://$APP_HOST:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
EOF"
  else
    sudo bash -c "cat > /etc/nginx/conf.d/ragapp.conf <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    location /$BASE_URL_PATH/ {
        proxy_pass http://$APP_HOST:$APP_PORT/$BASE_URL_PATH/;
        proxy_set_header Host \$host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
EOF"
  fi

  sudo setsebool -P httpd_can_network_connect 1
  sudo nginx -t
  sudo systemctl enable --now nginx
  sudo systemctl restart nginx
}

install_tls() {
  ensure_pkg snapd
  sudo systemctl enable --now snapd.socket
  sudo ln -s /var/lib/snapd/snap /snap 2>/dev/null || true
  sudo snap install --classic certbot
  sudo ln -sf /snap/bin/certbot /usr/bin/certbot
  # Replace email + domain
  sudo certbot --nginx -d "$SERVER_NAME" -m you@example.com --agree-tos --non-interactive
  sudo systemctl restart nginx
}

menu() {
  echo "RAGAPP (Oracle Linux 9) — Select step:"
  select opt in "Create user/dirs" "Python venv + deps" "Write env file" "Install systemd service" "Install Nginx (proxy)" "Enable TLS (certbot via snap)" "Quit"; do
    case $REPLY in
      1) create_user ;;
      2) setup_python ;;
      3) write_env ;;
      4) install_service ;;
      5) install_nginx ;;
      6) install_tls ;;
      7) exit 0 ;;
      *) echo "Invalid";;
    esac
  done
}

menu

