import subprocess
import sys

from btui import __version__
from btui.cli import main


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
