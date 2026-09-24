# TODO

## Doing
(sin task en curso; pendientes abajo)

## Next
- [ ] v0.7-verify: prueba real recepcion OPP desde telefono (radio on + listener activo en miniserver) - v0.7
- [ ] v1.0 DECISION: el bump entero a v1.0 (version + marketing + docs) lo decide el usuario, nunca automatico - v1.0

## Done
- [x] v0.12.5: fix TUI input — al abrir renombrar/enviar/recibir se setea mode=input; las teclas escriben y no disparan acciones de navegacion (k/j/q) - v0.12.5
- [x] v0.12.4: fix init_pair con fondo -1 (fallback 0 sin default colors) + attrs curses reales y header cyan bold - v0.12.4
- [x] v0.12.3: estetica con color (header cyan bold, titulos bold, seleccion reverse, tags trusted/known verdes/cyan, progreso azul, confirm rojo, hint dim; estilos deterministas line_style testeable; fallback monocromo) - v0.12.3
- [x] v0.12.2: prompt aceptar/cancelar en AuthorizePush solo para equipos no confiados (sin tty o timeout 60s -> rechaza; trusted auto-acepta) - v0.12.2
- [x] v0.12.1: fix recepcion OPP — rename al nombre real al completar (con colisiones a (N)), carpeta persistente configurable (config.py, /tmp/recibidos default), mensaje de fin por archivo "recibido: <ruta>" - v0.12.1
- [x] v0.11: TUI 3 secciones (cabecera / Mi adaptador / Dispositivos alrededor), menu contextual por equipo, radio on/off, gate de radio, receive desde la TUI, mensajes reales de connect - v0.11
- [x] v0.10.3: polish (--help agrupado por area + epilogo de ejemplos + errores uniformes) - v0.10.3
- [x] v0.10.2: menu curses front-end del CLI (--menu) - v0.10.2
- [x] v0.10.1: --check-update (git ls-remote vs version local) - v0.10.1
- [x] v0.9: TUI avanzado (navegacion hjkl, acciones p/t/x/c/i/s, detalle envio con progreso, ayuda ?) - v0.9
- [x] v0.8: TUI curses base (--tui): estado adaptador, conocidos, descubrimiento - v0.8
- [x] v0.6: envio OPP (--send=[files] [--to mac]) con progreso - v0.6
- [x] v0.5.1: adapter settings (--name/--discoverable/--pairable + --timeout) - v0.5.1
- [x] v0.5: dispositivos (--devices list/search/accept/deny + pair + conocidos) - v0.5
- [x] v0.4: --on/--off radio (power) - v0.4
- [x] v0.3: --info/--diagnose (driver, chip, hci, powered) - v0.3
- [x] v0.2: ciclo de vida CLI (--install/--update/--uninstall/--start/--stop/--restart) + servicio OpenRC + daemon placeholder - v0.2
- [x] v0.1: esqueleto btui (paquete, cli --version, install.sh minimo, tests) - v0.1