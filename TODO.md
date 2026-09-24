# TODO

# TODO

## Doing
(este milestone v0.10 esta cerrado: --menu, --check-update/--check-update y polish)

## Next
- [ ] v1.0 DECISION: al cerrar v0.10 las tags llegan a v0.10.x; el bump entero a v1.0 (version + marketing + docs) lo decide el usuario, nunca automatico - v1.0
- [ ] v0.7-verify: prueba real recepcion OPP desde telefono (codigo en v0.7/v0.7.1; kernel 6.18.52 con RFCOMM listo; listener probado en pty) - v0.7

## Done
- [x] v0.10.3: polish (--help agrupado por area + epilogo de ejemplos + errores uniformes) - v0.10.3
- [x] v0.10.2: menu curses front-end del CLI (--menu) - v0.10.2
- [x] v0.10.1: --check-update (git ls-remote vs version local) - v0.10.1
- [x] v0.9: TUI avanzado (navegacion hjkl, acciones p/t/x/c/i/s, detalle, envio con progreso, ayuda ?) - v0.9
- [x] v0.8: TUI curses base (--tui): estado adaptador, conocidos, descubrimiento - v0.8
- [x] v0.6: envio OPP (--send=[files] [--to mac]) con progreso - v0.6
- [x] v0.5.1: adapter settings (--name/--discoverable/--pairable + --timeout) - v0.5.1
- [x] v0.5: dispositivos (--devices list/search/accept/deny + pair + conocidos) - v0.5
- [x] v0.4: --on/--off radio (power) - v0.4
- [x] v0.3: --info/--diagnose (driver, chip, hci, powered) - v0.3
- [x] v0.2: ciclo de vida CLI (--install/--update/--uninstall/--start/--stop/--restart) + servicio OpenRC + daemon placeholder - v0.2
- [x] v0.1: esqueleto btui (paquete, cli --version, install.sh minimo, tests) - v0.1
