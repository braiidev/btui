import subprocess
import sys

from btui import __version__
from btui.cli import build_parser, main


def test_help_agrupa_flags() -> None:
    help_text = build_parser().format_help()
    for group in (
        "ciclo de vida",
        "interfaz",
        "adaptador",
        "dispositivos",
        "archivos (OPP)",
    ):
        assert group in help_text
    assert "ejemplos:" in help_text
    assert help_text.index("ciclo de vida") < help_text.index("archivos (OPP)")


def test_version_exit_code() -> None:
    assert main(["--version"]) == 0


def test_version_prints(capsys) -> None:
    main(["--version"])
    assert capsys.readouterr().out.strip() == f"btui {__version__}"


def test_module_version_flag() -> None:
    res = subprocess.run(
        [sys.executable, "-m", "btui", "--version"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert res.stdout.strip() == f"btui {__version__}"
