"""
Entry point for the `sjh` console script.
Keeps cli.py importable as a plain module while also being
discoverable by setuptools for the console_scripts entry point.
"""
from cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
