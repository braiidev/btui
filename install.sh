#!/bin/sh
# btui install.sh — instalador y ciclo de vida (v0.2).
set -e

VERSION="0.2"
REPO_URL="https://github.com/braiidev/btui.git"
REAL_USER="${SUDO_USER:-$USER}"
REAL_USER="${REAL_USER:-$(id -un)}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
SHARE_DIR="$REAL_HOME/.local/share/btui"
CONFIG_DIR="$REAL_HOME/.config/btui"
BIN_PATH="/usr/local/bin/btui"

log() { printf '[btui] %s\n' "$*"; }

PY="python3"

is_root() { [ "$(id -u)" -eq 0 ]; }

install_code() {
	log "codigo -> $SHARE_DIR"
	mkdir -p "$SHARE_DIR"
	if [ -d "$SHARE_DIR/.git" ]; then
		git -C "$SHARE_DIR" pull --ff-only
	else
		git clone "$REPO_URL" "$SHARE_DIR"
	fi
}

setup_venv() {
	if python3 -m venv "$SHARE_DIR/.venv" 2>/dev/null; then
		"$SHARE_DIR/.venv/bin/pip" install --quiet -r "$SHARE_DIR/requirements.txt"
		PY="$SHARE_DIR/.venv/bin/python"
	else
		log "AVISO: venv no disponible; uso el python del sistema."
	fi
}

install_wrapper() {
	mkdir -p "$SHARE_DIR/bin"
	wrapper="$SHARE_DIR/bin/btui"
	cat > "$wrapper" <<EOF
#!/bin/sh
# btui wrapper
cd "$SHARE_DIR"
exec "$PY" -m btui "\$@"
EOF
	chmod +x "$wrapper"
	if is_root; then
		install -m 0755 "$wrapper" "$BIN_PATH"
	elif command -v sudo >/dev/null 2>&1; then
		sudo install -m 0755 "$wrapper" "$BIN_PATH"
	else
		log "AVISO: sin root no se enlaza $BIN_PATH; usa el wrapper manual:"
		log "  $wrapper --version"
		return 0
	fi
	log "binario -> $BIN_PATH"
}

install_service() {
	mkdir -p "$CONFIG_DIR"
	if ! is_root; then
		log "AVISO: sin root no se instala el servicio OpenRC."
		return 0
	fi
	tmp_init="/tmp/btui.initd"
	cat > "$tmp_init" <<EOF
#!/sbin/openrc-run
name="btui daemon"
description="Daemon de gestion Bluetooth (btui)"
command="$BIN_PATH"
command_args="daemon"
command_user="$REAL_USER"
command_background=true
command_env="HOME=$REAL_HOME"
pidfile="$CONFIG_DIR/btui.pid"
depend() {
    need dbus bluetooth
}
EOF
	install -m 0755 "$tmp_init" /etc/init.d/btui
	rc-update add btui default 2>/dev/null || true
	grep -q "$BIN_PATH" /etc/sudoers.d/btui 2>/dev/null || \
		printf '%s\n' "$REAL_USER ALL=(root) NOPASSWD: $BIN_PATH" > /etc/sudoers.d/btui
	chmod 0440 /etc/sudoers.d/btui
	if ! rc-service btui status >/dev/null 2>&1; then
		rc-service btui start
	fi
	log "servicio btui activo (OpenRC + sudoers NOPASSWD listos)"
}

uninstall() {
	if is_root; then
		rc-service btui stop 2>/dev/null || true
		rc-update del btui default 2>/dev/null || true
		rm -f /etc/init.d/btui /etc/sudoers.d/btui "$BIN_PATH"
		log "servicio, sudoers y binario removidos."
		log "Se conservan datos: $CONFIG_DIR (y codigo en $SHARE_DIR)"
	elif command -v sudo >/dev/null 2>&1; then
		sudo sh "$SHARE_DIR/install.sh" --uninstall
	else
		log "ERROR: no hay root ni sudo para desinstalar."
	fi
}

case "$1" in
--version)
	echo "btui $VERSION"
	;;
--update)
	install_code
	setup_venv
	install_wrapper
	if is_root && rc-service btui status >/dev/null 2>&1; then
		rc-service btui restart
	fi
	log "actualizado."
	;;
--uninstall)
	uninstall
	;;
--check-update)
	log "chequeo de update llega en v0.10"
	;;
*)
	install_code
	setup_venv
	install_wrapper
	install_service
	log "listo (v0.2)."
	;;
esac