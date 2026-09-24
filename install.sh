#!/bin/sh
# btui install.sh — instalador minimo (v0.1: esqueleto + --version).
# Ciclo de vida completo (update/uninstall/servicio) llega en v0.2.
set -e

VERSION="0.1"
REPO_URL="https://github.com/braiidev/btui.git"
REAL_USER="${SUDO_USER:-$USER}"
REAL_USER="${REAL_USER:-$(id -un)}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
SHARE_DIR="$REAL_HOME/.local/share/btui"
BIN_PATH="/usr/local/bin/btui"

log() { printf '[btui] %s\n' "$*"; }

PY="python3"

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
	wrapper="$SHARE_DIR/btui"
	cat > "$wrapper" <<EOF
#!/bin/sh
# btui wrapper
cd "$SHARE_DIR"
exec "$PY" -m btui "\$@"
EOF
	chmod +x "$wrapper"
	if [ "$(id -u)" -eq 0 ] || sudo -n true 2>/dev/null; then
		sudo install -m 0755 "$wrapper" "$BIN_PATH"
		log "binario -> $BIN_PATH"
	else
		log "AVISO: sin root no se enlaza $BIN_PATH; usa el wrapper manual:"
		log "  $wrapper --version"
	fi
}

case "$1" in
--version)
	echo "btui $VERSION"
	;;
--check-update)
	log "chequeo de update llega en v0.2"
	;;
*)
	install_code
	setup_venv
	install_wrapper
	log "listo (v0.1)."
	;;
esac