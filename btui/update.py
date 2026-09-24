"""Chequeo de actualizaciones de btui contra el remoto git.

La logica de parseo/comparacion es pura (parse_version, parse_tags, latest,
compare) para testearla sin red. run() ejecuta `git ls-remote --tags` sobre el
repo instalado y reporta.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from btui import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)$")


def parse_version(text: str) -> tuple[int, ...] | None:
    match = VERSION_RE.match(text.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def parse_tags(output: str) -> list[str]:
    tags: list[str] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/") :]
        if name.endswith("^{}"):
            name = name[:-3]
        if name not in tags:
            tags.append(name)
    return tags


def latest(tags: list[str]) -> str | None:
    best: tuple[tuple[int, ...], str] | None = None
    for tag in tags:
        version = parse_version(tag)
        if version is None:
            continue
        if best is None or version > best[0]:
            best = (version, tag)
    return best[1] if best else None


def compare(local: str, remote: str) -> int:
    lv = parse_version(local)
    rv = parse_version(remote)
    if lv is None or rv is None:
        return 0
    if rv > lv:
        return -1
    if rv < lv:
        return 1
    return 0


def run(remote: str = "origin") -> int:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-remote", "--tags", remote],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("error: git no esta disponible", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("error: timeout consultando el remoto", file=sys.stderr)
        return 2
    if proc.returncode != 0:
        print(f"error: no se pudo consultar {remote}", file=sys.stderr)
        return 2
    remote_version = latest(parse_tags(proc.stdout))
    if remote_version is None:
        print("error: el remoto no tiene tags de version", file=sys.stderr)
        return 2
    if compare(__version__, remote_version) < 0:
        shown = remote_version[1:] if remote_version.startswith("v") else remote_version
        print(f"hay v{shown} disponible (actual {__version__})")
        return 1
    print(f"btui {__version__} al dia (remoto {remote_version})")
    return 0
