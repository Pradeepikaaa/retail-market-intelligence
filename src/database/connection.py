from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from dotenv import dotenv_values
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)


def load_database_settings(
    env_file: Optional[Path] = None,
) -> DatabaseSettings:
    """Load MySQL settings from the environment or the local .env file."""
    config_path = env_file or PROJECT_ROOT / ".env"
    if env_file is not None and not config_path.is_file():
        raise FileNotFoundError(f"Environment file not found: {config_path}")
    file_values = dotenv_values(config_path)

    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    values = {}
    for name in required:
        process_value = os.getenv(name)
        values[name] = (
            process_value
            if process_value not in (None, "")
            else file_values.get(name)
        )
    missing = [name for name in required if values[name] is None]
    if missing:
        raise ValueError(
            "Missing database settings: "
            + ", ".join(missing)
            + ". Set them in the ignored local .env file."
        )

    host = str(values["DB_HOST"]).strip()
    database = str(values["DB_NAME"]).strip()
    username = str(values["DB_USER"]).strip()
    if not host:
        raise ValueError("DB_HOST must not be blank.")
    if not username:
        raise ValueError("DB_USER must not be blank.")
    if not database or not database.replace("_", "").isalnum():
        raise ValueError("DB_NAME must contain only letters, numbers, and underscores.")

    try:
        port = int(str(values["DB_PORT"]))
    except ValueError as exc:
        raise ValueError("DB_PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be between 1 and 65535.")

    return DatabaseSettings(
        host=host,
        port=port,
        database=database,
        username=username,
        password=str(values["DB_PASSWORD"]),
    )


def create_database_engine(settings: DatabaseSettings) -> Engine:
    """Create a MySQL engine without logging credentials."""
    url = URL.create(
        "mysql+pymysql",
        username=settings.username,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.database,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def test_connection(env_file: Optional[Path] = None) -> None:
    settings = load_database_settings(env_file)
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
            if result != 1:
                raise RuntimeError("MySQL returned an unexpected connection-test result.")
    finally:
        engine.dispose()
    LOGGER.info(
        "MySQL connection succeeded: host=%s port=%s database=%s",
        settings.host,
        settings.port,
        settings.database,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test the configured MySQL connection."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional path to a local environment file (defaults to project .env).",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        test_connection(args.env_file)
    except Exception:
        LOGGER.exception("MySQL connection test failed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
