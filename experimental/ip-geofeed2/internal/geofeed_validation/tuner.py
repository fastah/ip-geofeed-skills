import json
import uuid
import urllib.request
from typing import Optional

from internal.parser.parser import Row

from .validator import (
    Entry, Location, ValidationContext,
    check_for_issues,
)


class PlaceSearchRow:
    """Represents a single row in the place search request."""
    def __init__(self, row_key: str = "", country_code: str = "",
                 region_code: str = "", city_name: str = "", search_mode: str = ""):
        self.row_key = row_key
        self.country_code = country_code
        self.region_code = region_code
        self.city_name = city_name
        self.search_mode = search_mode

    def to_dict(self) -> dict:
        return {
            "rowKey": self.row_key,
            "countryCode": self.country_code,
            "regionCode": self.region_code,
            "cityName": self.city_name,
            "searchMode": self.search_mode,
        }


def _call_place_search_api(rows: list[PlaceSearchRow]) -> list[dict]:
    """Makes an HTTP POST request to the place-search API."""
    api_url = "https://mcp.fastah.ai/rest/geofeeds/place-search"

    request_body = json.dumps({"rows": [r.to_dict() for r in rows]}).encode("utf-8")

    req = urllib.request.Request(api_url, data=request_body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            raise RuntimeError(f"API returned status {resp.status}")
        response_data = json.loads(resp.read().decode("utf-8"))

    return response_data.get("results", [])


def get_entries_from_server(entry_rows: list[Row], ctx: ValidationContext) -> tuple[list[Entry], list[Entry]]:
    """Fetches tuning data from the API and builds Entry objects."""
    MAX_BATCH_SIZE = 1000

    entries: list[Entry] = []
    rows: list[PlaceSearchRow] = []
    err_entries: list[Entry] = []
    deduplicate_map: dict[str, list[int]] = {}
    deduplicate_uuid_map: dict[str, list[int]] = {}

    for i, row in enumerate(entry_rows):
        country_code = row.country_code
        region_code = row.region_code
        city = row.city

        # If all geolocation fields are empty, set country code to "ZZ"
        if not country_code and not region_code and not city:
            country_code = "ZZ"

        key = f"{country_code}|{region_code}|{city}"
        if key not in deduplicate_map:
            deduplicate_map[key] = [i]
        else:
            deduplicate_map[key].append(i)

        entries.append(Entry(
            line=row.line,
            ip_prefix=row.ip_prefix,
            country_code=country_code,
            region_code=region_code,
            city=city,
            postal_code=row.postal_code,
        ))

    for indices in deduplicate_map.values():
        uid = str(uuid.uuid4())
        deduplicate_uuid_map[uid] = indices

    for uid, indices in deduplicate_uuid_map.items():
        sample = entry_rows[indices[0]]
        rows.append(PlaceSearchRow(
            row_key=uid,
            country_code=sample.country_code,
            region_code=sample.region_code,
            city_name=sample.city,
            search_mode="auto",
        ))

    if not rows:
        return entries, err_entries

    # Process in batches
    for batch_start in range(0, len(rows), MAX_BATCH_SIZE):
        batch_end = min(batch_start + MAX_BATCH_SIZE, len(rows))
        batch_rows = rows[batch_start:batch_end]

        try:
            results = _call_place_search_api(batch_rows)
        except Exception as e:
            print(f"Warning: Failed to call place-search API for batch {batch_start}-{batch_end}: {e}")
            continue

        for result in results:
            matches = result.get("matches", [])
            is_dng = result.get("isExplicitlyDoNotGeolocate", False)
            row_key = result.get("rowKey", "")

            if matches and not is_dng:
                match = matches[0]
                match_country = match.get("countryCode", "")
                match_region = match.get("stateCode", "")

                if check_for_issues(match_country, match_region, ctx):
                    if row_key in deduplicate_uuid_map:
                        err_entries.append(entries[deduplicate_uuid_map[row_key][0]])
                    continue

                location = Location(
                    name=match.get("placeName", ""),
                    country_code=match_country,
                    region_code=match_region,
                    place_type=match.get("placeType", ""),
                    h3_cells=match.get("h3Cells", []),
                    bounding_box=match.get("boundingBox", []),
                )

                if row_key in deduplicate_uuid_map:
                    for entry_idx in deduplicate_uuid_map[row_key]:
                        entries[entry_idx].tuned_entry = location

    return entries, err_entries
