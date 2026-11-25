from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import List, Optional, Sequence, Union


SUPPORTED_EXTENSIONS = frozenset({".csv", ".xls", ".xlsx"})


def _safe_target_path(member_name: str, output_root: Path) -> Path:
    normalized_name = member_name.replace("\\", "/")
    member_path = PurePosixPath(normalized_name)
    if (
        member_path.is_absolute()
        or not member_path.parts
        or any(part == ".." or ":" in part for part in member_path.parts)
    ):
        raise ValueError(f"Unsafe ZIP member path: {member_name}")

    target = (output_root / Path(*member_path.parts)).resolve()
    try:
        target.relative_to(output_root)
    except ValueError as exc:
        raise ValueError(f"ZIP member escapes extraction directory: {member_name}") from exc
    return target


def extract_dataset_files(
    archive_path: Union[str, Path],
    output_dir: Union[str, Path],
    overwrite: bool = False,
) -> List[Path]:
    archive = Path(archive_path)
    if not archive.is_file():
        raise FileNotFoundError(f"Archive not found: {archive}")
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"Not a valid ZIP archive: {archive}")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    output_root = output_root.resolve()

    with zipfile.ZipFile(archive) as zip_file:
        members = [
            member
            for member in zip_file.infolist()
            if not member.is_dir()
            and PurePosixPath(member.filename.replace("\\", "/")).suffix.casefold()
            in SUPPORTED_EXTENSIONS
        ]
        if not members:
            raise ValueError(
                f"No CSV, XLS, or XLSX files found in archive: {archive}"
            )

        targets = []
        seen_targets = set()
        for member in members:
            target = _safe_target_path(member.filename, output_root)
            if target in seen_targets:
                raise ValueError(f"Duplicate ZIP member path: {member.filename}")
            if target.exists() and not overwrite:
                raise FileExistsError(
                    f"Refusing to overwrite existing extracted file: {target}. "
                    "Pass overwrite=True to replace it."
                )
            seen_targets.add(target)
            targets.append((member, target))

        extracted = []
        for member, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary_path: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    dir=str(target.parent),
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    with zip_file.open(member) as source:
                        shutil.copyfileobj(source, temporary_file)

                if target.exists() and not overwrite:
                    raise FileExistsError(
                        f"Refusing to overwrite existing extracted file: {target}"
                    )
                os.replace(temporary_path, target)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
            extracted.append(target)

    return extracted


def main(argv: Optional[Sequence[str]] = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Extract CSV, XLS, and XLSX files from a ZIP archive."
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=project_root / "data" / "raw" / "archive.zip",
        help="Path to the source ZIP archive.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "data" / "raw" / "extracted",
        help="Directory for extracted dataset files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace dataset files already present in the output directory.",
    )
    args = parser.parse_args(argv)

    extracted = extract_dataset_files(args.archive, args.output_dir, args.overwrite)
    print(f"Extracted {len(extracted)} dataset file(s):")
    for path in extracted:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
