#!/usr/bin/env bash
# =============================================================================
# Установка Telegram MTProto WebSocket прокси на Oracle Cloud (Ubuntu/Debian)
# Запуск: bash <(curl -fsSL https://raw.githubusercontent.com/rafael-mansurov/tg-ws-proxy-android/main/setup-vps.sh)
# =============================================================================
set -euo pipefail

PROXY_DIR="/opt/tg-ws-proxy"
SERVICE="tg-ws-proxy"
PORT=1443
SECRET_FILE="/etc/tg-ws-proxy.secret"
REPO="https://github.com/rafael-mansurov/tg-ws-proxy-android.git"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
section() { echo -e "\n${GREEN}══ $* ══${NC}"; }

# ── root check ────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}Запусти скрипт от root: sudo bash setup-vps.sh${NC}"
  exit 1
fi

section "Установка зависимостей"
apt-get update -qq
apt-get install -y -qq python3 python3-pip git curl iptables-persistent 2>/dev/null || \
  apt-get install -y -qq python3 python3-pip git curl
pip3 install -q cryptography
info "Python + cryptography установлены"

section "Загрузка прокси"
if [[ -d "$PROXY_DIR/.git" ]]; then
  git -C "$PROXY_DIR" pull -q
  info "Репозиторий обновлён"
else
  rm -rf "$PROXY_DIR"
  git clone -q "$REPO" "$PROXY_DIR"
  info "Репозиторий клонирован"
fi

section "Секрет прокси"
if [[ -f "$SECRET_FILE" ]]; then
  SECRET=$(cat "$SECRET_FILE")
  info "Используется существующий секрет"
else
  SECRET=$(python3 -c "import os; print(os.urandom(16).hex())")
  echo "$SECRET" > "$SECRET_FILE"
  chmod 600 "$SECRET_FILE"
  info "Создан новый секрет"
fi

section "Systemd сервис"
cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=Telegram MTProto WebSocket Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROXY_DIR}
ExecStart=/usr/bin/python3 -m proxy.tg_ws_proxy --host 0.0.0.0 --port ${PORT} --secret ${SECRET}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tg-ws-proxy

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
sleep 2
if systemctl is-active --quiet "$SERVICE"; then
  info "Сервис запущен"
else
  warn "Сервис не запустился. Проверь: journalctl -u $SERVICE -n 30"
fi

section "Брандмауэр"
iptables  -I INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null || true
ip6tables -I INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null || true
# Сохраняем
if command -v netfilter-persistent &>/dev/null; then
  netfilter-persistent save 2>/dev/null || true
elif command -v iptables-save &>/dev/null; then
  iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
fi
info "Порт $PORT открыт"

section "Публичный IP"
PUBLIC_IP=$(curl -s --max-time 6 https://api.ipify.org \
         || curl -s --max-time 6 https://ifconfig.me \
         || echo "")
if [[ -z "$PUBLIC_IP" ]]; then
  warn "Не удалось определить IP. Подставь IP вручную."
  PUBLIC_IP="ВАШ_VPS_IP"
fi
info "IP: $PUBLIC_IP"

# ── итог ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ПРОКСИ ГОТОВ                                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  IP сервера : ${YELLOW}${PUBLIC_IP}${NC}"
echo -e "  Порт       : ${YELLOW}${PORT}${NC}"
echo -e "  Secret     : ${YELLOW}${SECRET}${NC}"
echo ""
echo -e "  Ссылка для Telegram:"
echo -e "  ${YELLOW}tg://proxy?server=${PUBLIC_IP}&port=${PORT}&secret=dd${SECRET}${NC}"
echo ""
echo -e "${YELLOW}⚠  Oracle Cloud: в Security List добавь правило Ingress TCP порт ${PORT}${NC}"
echo ""
echo -e "  Управление сервисом:"
echo -e "    journalctl -u $SERVICE -f   # логи"
echo -e "    systemctl restart $SERVICE  # перезапуск"
echo -e "    cat $SECRET_FILE            # показать секрет"
echo ""
