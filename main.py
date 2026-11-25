"""Streamlit entry point for the retail market intelligence project."""

from streamlit.web import cli as stcli
import sys


def main() -> None:
    sys.argv = ["streamlit", "run", "app.py"]
    stcli.main()


if __name__ == "__main__":
    main()
