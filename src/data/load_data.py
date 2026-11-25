from pathlib import Path
from typing import List, Union

import pandas as pd


SUPPORTED_EXTENSIONS = frozenset({".csv", ".xls", ".xlsx"})


def discover_dataset_files(path: Union[str, Path]) -> List[Path]:
    dataset_path = Path(path)
    if dataset_path.is_file():
        if dataset_path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported dataset format: {dataset_path}")
        return [dataset_path]

    if not dataset_path.is_dir():
        raise FileNotFoundError(f"Dataset path does not exist: {dataset_path}")

    files = sorted(
        candidate
        for candidate in dataset_path.rglob("*")
        if candidate.is_file()
        and candidate.suffix.casefold() in SUPPORTED_EXTENSIONS
    )
    if not files:
        raise FileNotFoundError(
            f"No CSV, XLS, or XLSX dataset files found under: {dataset_path}"
        )
    return files


def load_data(path: Union[str, Path]) -> pd.DataFrame:
    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    extension = dataset_path.suffix.casefold()
    if extension == ".csv":
        try:
            return pd.read_csv(dataset_path, encoding="utf-8-sig", low_memory=False)
        except UnicodeDecodeError:
            return pd.read_csv(dataset_path, encoding="cp1252", low_memory=False)
    if extension in {".xls", ".xlsx"}:
        return pd.read_excel(dataset_path)

    raise ValueError(f"Unsupported dataset format: {dataset_path}")
