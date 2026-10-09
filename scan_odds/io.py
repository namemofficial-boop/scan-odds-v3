"""Load odds snapshots from JSON or CSV."""
import csv
import json
from pathlib import Path

from .models import OddsRow


def load_rows(path: str | Path) -> list[OddsRow]:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Input file not found: {file}")
    if file.suffix.lower() == ".json":
        data = json.loads(file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("odds", data.get("rows"))
        if not isinstance(data, list):
            raise ValueError("JSON input must be a list or an object with an 'odds'/'rows' list")
        return [OddsRow.from_mapping(item) for item in data]
    if file.suffix.lower() == ".csv":
        with file.open(newline="", encoding="utf-8-sig") as stream:
            return [OddsRow.from_mapping(row) for row in csv.DictReader(stream)]
    raise ValueError("Input must be .json or .csv")
