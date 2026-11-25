from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Sequence

from src.data.preprocess import PreprocessingConfig, run_preprocessing


LOGGER = logging.getLogger(__name__)


def main(argv: Optional[Sequence[str]] = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Preprocess retail transactions into analysis-ready datasets."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=project_root / "data" / "raw" / "extracted",
        help="Raw CSV, XLS, XLSX file, or directory containing exactly one dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "data" / "processed",
        help="Directory for analysis-ready output datasets.",
    )
    parser.add_argument(
        "--snapshot-date",
        help="Optional ISO 8601 RFM reference date; defaults to one day after the "
        "latest eligible sale.",
    )
    parser.add_argument(
        "--cancellation-prefix",
        default="C",
        help="Invoice prefix used to identify cancellations (default: C).",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="Logging verbosity.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = PreprocessingConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        snapshot_date=args.snapshot_date,
        cancellation_prefix=args.cancellation_prefix,
    )
    try:
        result = run_preprocessing(config)
    except Exception:
        LOGGER.exception("Retail data preprocessing failed.")
        raise

    LOGGER.info("Preprocessing completed successfully.")
    for dataset_name, path in result.output_paths.items():
        LOGGER.info("Output - %s: %s", dataset_name, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
