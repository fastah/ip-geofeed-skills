import csv
import io
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Row:
    """Represents a single CSV row."""
    line: int = 0
    ip_prefix: str = ""
    country_code: str = ""
    region_code: str = ""
    city: str = ""
    postal_code: str = ""


@dataclass
class Record:
    """Represents a single geofeed entry from publishers JSON."""
    geofeed: str = ""
    inetnum: str = ""
    source: str = ""
    netname: str = ""
    country: str = ""
    org: str = ""
    admin_c: str = ""
    tech_c: str = ""
    mnt_by: str = ""
    city: str = ""

    def encode_inetnum(self) -> str:
        """Encodes the inetnum field into a filesystem-friendly string."""
        s = self.inetnum.strip()
        s = s.replace(" - ", "_to_")
        s = s.replace(".", "-")
        s = s.replace(":", "-")
        s = s.replace("/", "-")
        s = re.sub(r"[^a-zA-Z0-9\-_]+", "", s)
        return s


def load_publishers(file_path: str) -> list[Record]:
    """Reads and unmarshals a publishers.json file."""
    with open(file_path, "r") as f:
        data = json.load(f)

    publishers = []
    for item in data:
        publishers.append(Record(
            geofeed=item.get("geofeed", ""),
            inetnum=item.get("inetnum", ""),
            source=item.get("source", ""),
            netname=item.get("netname", ""),
            country=item.get("country", ""),
            org=item.get("org", ""),
            admin_c=item.get("admin-c", ""),
            tech_c=item.get("tech-c", ""),
            mnt_by=item.get("mnt-by", ""),
            city=item.get("city", ""),
        ))
    return publishers


def _is_url(file_source: str) -> bool:
    """Checks if the given string is a valid HTTP/HTTPS URL."""
    parsed = urllib.parse.urlparse(file_source)
    return parsed.scheme in ("http", "https")


def _download_file(url_str: str) -> str:
    """Downloads a file from a URL and saves it to the run/data folder."""
    run_data_dir = os.path.join("run", "data")
    os.makedirs(run_data_dir, exist_ok=True)

    parsed = urllib.parse.urlparse(url_str)
    filename = os.path.basename(parsed.path)
    if not filename or filename in ("/", "."):
        filename = "geofeed.csv"

    output_path = os.path.join(run_data_dir, filename)

    req = urllib.request.Request(url_str)
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; IPGeofeed/1.0)")
    req.add_header("Accept", "*/*")

    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Download failed with status {resp.status}: {url_str}")
        with open(output_path, "wb") as out:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                out.write(chunk)

    return output_path


def _resolve_file_path(file_source: str) -> str:
    """Resolves the actual file path, downloading from URL if necessary."""
    if _is_url(file_source):
        print(f"Downloading from URL: {file_source}")
        return _download_file(file_source)
    return file_source


def parse_csv(file_source: str, limit: int = 0) -> tuple[list[Row], dict[int, str], int]:
    """Reads and parses a CSV geofeed file from local path or URL.

    Returns:
        Tuple of (rows, comments, invalid_entries)
    """
    filepath = _resolve_file_path(file_source)

    rows: list[Row] = []
    comments: dict[int, str] = {}
    line_num = 0
    invalid_entries = 0
    valid_entries = 0

    with open(filepath, "r", newline="") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            trimmed = line.strip()
            line_num += 1

            if trimmed == "":
                comments[line_num] = line
                continue
            if trimmed.startswith("#"):
                comments[line_num] = line
                continue

            if limit > 0 and valid_entries >= limit:
                break

            try:
                reader = csv.reader(io.StringIO(line), skipinitialspace=True)
                record = next(reader)
            except (csv.Error, StopIteration):
                continue

            if len(record) < 4 or len(record) > 5:
                invalid_entries += 1
                continue

            row = Row(
                line=line_num,
                ip_prefix=record[0].strip(),
                country_code=record[1].strip(),
                region_code=record[2].strip(),
                city=record[3].strip(),
            )
            if len(record) == 5:
                row.postal_code = record[4].strip()

            rows.append(row)
            valid_entries += 1

    return rows, comments, invalid_entries
