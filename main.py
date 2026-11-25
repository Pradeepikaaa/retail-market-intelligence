"""Streamlit entry point for the retail market intelligence project."""

from pathlib import Path
import runpy
import sys

from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli

APP_PATH = Path(__file__).with_name("app.py")


def main() -> None:
    if get_script_run_ctx(suppress_warning=True) is not None:
        runpy.run_path(str(APP_PATH))
        return

    sys.argv = ["streamlit", "run", "app.py"]
    stcli.main()


if __name__ == "__main__":
    main()
