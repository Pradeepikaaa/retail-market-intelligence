"""Streamlit entry point for the retail market intelligence project."""

import sys
from importlib import import_module

from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli


def main() -> None:
    if get_script_run_ctx(suppress_warning=True) is not None:
        import_module("app")
        return

    sys.argv = ["streamlit", "run", "app.py"]
    stcli.main()


if __name__ == "__main__":
    main()
