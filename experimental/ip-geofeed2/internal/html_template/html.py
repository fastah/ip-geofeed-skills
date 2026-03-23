import json
import os

from jinja2 import Environment, FileSystemLoader

from internal.geofeed_validation.validator import Entry, Metadata, Netname, ValidatorRecord


_TEMPLATE_DIR = os.path.join("internal", "html_template", "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def generate_html_report(
    entries: list[Entry],
    comments: dict[int, str],
    metadata: Metadata,
    path: str,
) -> None:
    """Generates an HTML validation report from entries."""
    tmpl = _env.get_template("report.html")

    comments_json = json.dumps(comments)

    html = tmpl.render(
        entries=entries,
        comments_json=comments_json,
        metadata=metadata,
    )

    file_path = os.path.join("run", "output", path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        f.write(html)


def generate_netname_html_table(records: list[ValidatorRecord], path: str) -> None:
    """Generates an HTML table for netname records."""
    tmpl = _env.get_template("netname_table.html")

    html = tmpl.render(records=records)

    file_path = os.path.join("run", "output", path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        f.write(html)


def generate_source_html_table(netnames: list[Netname], source: str, path: str) -> None:
    """Generates an HTML table for source/RIR records."""
    tmpl = _env.get_template("source_table.html")

    html = tmpl.render(netnames=netnames, source=source)

    file_path = os.path.join("run", "output", path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as f:
        f.write(html)
