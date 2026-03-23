import ipaddress
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from internal.parser.parser import Row, Record

from .errors import (
    ERROR_TYPE, WARNING_TYPE, SUGGEST_TYPE,
    ERR_IP_PREFIX_EMPTY, ERR_IP_PREFIX_INVALID, ERR_IP_PREFIX_NON_PUBLIC,
    SUGGEST_IPV4_PREFIX_LARGE, SUGGEST_IPV6_PREFIX_LARGE,
    ERR_COUNTRY_CODE_INVALID,
    ERR_REGION_CODE_FORMAT, ERR_REGION_CODE_INVALID, ERR_REGION_CODE_MISMATCH,
    ERR_CITY_PLACEHOLDER, ERR_CITY_ABBREVIATED, WARN_CITY_FORMATTING_BAD,
    ERR_POSTAL_CODE_DEPRECATED,
    SUGGEST_REGION_UNNECESSARY_SMALL_TERRITORY, SUGGEST_CITY_UNNECESSARY_SMALL_TERRITORY,
    SUGGEST_REGION_RECOMMENDED_WITH_CITY, SUGGEST_CONFIRM_DO_NOT_GEOLOCATE,
    ValidationError,
)

PLACEHOLDER_VALUES = ["undefined", "please select", "null", "n/a", "tbd", "unknown"]
ABBREVIATED_VALUES = ["la", "frft", "sin01", "lhr", "sin", "maa"]

# IPv4 private ranges
_IPV4_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

# IPv6 private ranges
_IPV6_PRIVATE_RANGES = [
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
]


@dataclass
class Country:
    """Represents an ISO 3166-1 country."""
    alpha_2: str = ""
    alpha_3: str = ""
    flag: str = ""
    name: str = ""
    numeric: str = ""
    official_name: str = ""


@dataclass
class Region:
    """Represents an ISO 3166-2 subdivision."""
    code: str = ""
    name: str = ""
    type: str = ""


@dataclass
class ValidationContext:
    """Holds all validation data."""
    countries: dict[str, Country] = field(default_factory=dict)
    regions: dict[str, Region] = field(default_factory=dict)
    small_territories: dict[str, bool] = field(default_factory=dict)


@dataclass
class Message:
    """Represents a validation issue."""
    id: str = ""
    type: str = ""
    text: str = ""
    checked: bool = False


@dataclass
class Location:
    """Represents a geographic location match."""
    name: str = ""
    country_code: str = ""
    region_code: str = ""
    place_type: str = ""
    h3_cells: list[str] = field(default_factory=list)
    bounding_box: list[float] = field(default_factory=list)


@dataclass
class Entry:
    """Represents a single CSV row with validation results."""
    # From Row
    line: int = 0
    ip_prefix: str = ""
    country_code: str = ""
    region_code: str = ""
    city: str = ""
    postal_code: str = ""
    # Validation fields
    status: str = ""
    messages: list[Message] = field(default_factory=list)
    has_error: bool = False
    has_warning: bool = False
    has_suggestion: bool = False
    ip_version: str = ""
    do_not_geolocate: bool = False
    geocoding_hint: str = ""
    tunable: bool = False
    tuned_entry: Optional[Location] = None

    def add_status_message(self, msg: ValidationError):
        self.messages.append(Message(
            id=msg.id,
            type=msg.type,
            text=msg.message,
            checked=msg.tunable,
        ))
        self.tunable = self.tunable or msg.tunable
        if msg.type == ERROR_TYPE:
            self.has_error = True
        elif msg.type == WARNING_TYPE:
            self.has_warning = True
        elif msg.type == SUGGEST_TYPE:
            self.has_suggestion = True


@dataclass
class Metadata:
    """Represents summary information."""
    input_file: str = ""
    timestamp: int = 0
    total_entries: int = 0
    ipv4_entries: int = 0
    ipv6_entries: int = 0
    invalid_entries: int = 0
    errors: int = 0
    warnings: int = 0
    suggestions: int = 0
    ok: int = 0
    city_level_accuracy: int = 0
    region_level_accuracy: int = 0
    country_level_accuracy: int = 0
    do_not_geolocate: int = 0


@dataclass
class ValidatorRecord:
    """Wraps a parser Record with a report URL."""
    record: Record = field(default_factory=Record)
    report_url: str = ""


@dataclass
class Netname:
    """Represents a grouping of geofeeds by netname."""
    name: str = ""
    records: list[ValidatorRecord] = field(default_factory=list)
    table_url: str = ""


@dataclass
class RIR:
    """Represents a Regional Internet Registry with its associated netnames."""
    name: str = ""
    netnames: dict[str, Netname] = field(default_factory=dict)


@dataclass
class RIRCollection:
    """Represents all Regional Internet Registries."""
    rirs: dict[str, RIR] = field(default_factory=dict)


def load_validation_data() -> ValidationContext:
    """Loads ISO and territorial data from JSON files."""
    ctx = ValidationContext()

    # Load ISO 3166-1 countries
    with open("internal/geofeed_validation/iso3166-1.json", "r") as f:
        countries_data = json.load(f)
    for c in countries_data.get("3166-1", []):
        country = Country(
            alpha_2=c.get("alpha_2", ""),
            alpha_3=c.get("alpha_3", ""),
            flag=c.get("flag", ""),
            name=c.get("name", ""),
            numeric=c.get("numeric", ""),
            official_name=c.get("official_name", ""),
        )
        ctx.countries[country.alpha_2] = country

    # Load ISO 3166-2 regions
    with open("internal/geofeed_validation/iso3166-2.json", "r") as f:
        regions_data = json.load(f)
    for r in regions_data.get("3166-2", []):
        region = Region(
            code=r.get("code", ""),
            name=r.get("name", ""),
            type=r.get("type", ""),
        )
        ctx.regions[region.code] = region

    # Load small territories
    with open("internal/geofeed_validation/small-territories.json", "r") as f:
        territories = json.load(f)
    for t in territories:
        ctx.small_territories[t] = True

    return ctx


def validate_entries(rows: list[Row]) -> tuple[list[Entry], list[Entry]]:
    """Validates a list of entries and populates their messages and status."""
    from .tuner import get_entries_from_server

    ctx = load_validation_data()
    entries, err_entries = get_entries_from_server(rows, ctx)

    for entry in entries:
        validate_entry(entry, ctx)

    return entries, err_entries


def get_metadata_from_entries(entries: list[Entry], input_file: str, invalid_entries: int) -> Metadata:
    """Computes metadata summary from validated entries."""
    metadata = Metadata(
        input_file=input_file,
        timestamp=int(time.time() * 1000),
        invalid_entries=invalid_entries,
    )

    for entry in entries:
        metadata.total_entries += 1
        if entry.ip_version == "IPv4":
            metadata.ipv4_entries += 1
        elif entry.ip_version == "IPv6":
            metadata.ipv6_entries += 1

        if entry.has_error:
            metadata.errors += 1
        elif entry.has_warning:
            metadata.warnings += 1
        elif entry.has_suggestion:
            metadata.suggestions += 1
        else:
            metadata.ok += 1

        if entry.city:
            metadata.city_level_accuracy += 1
        elif entry.region_code:
            metadata.region_level_accuracy += 1
        elif entry.country_code:
            metadata.country_level_accuracy += 1

        if entry.do_not_geolocate:
            metadata.do_not_geolocate += 1

    return metadata


def validate_entry(entry: Entry, ctx: ValidationContext):
    """Validates a single entry and populates its messages."""
    validate_ip_prefix(entry)
    validate_country_code(entry, ctx)
    validate_region_code(entry, ctx)
    validate_city_name(entry, ctx)
    validate_postal_code(entry)
    provide_tuning_recommendations(entry, ctx)

    if entry.has_error:
        entry.status = "ERROR"
    elif entry.has_warning:
        entry.status = "WARNING"
    elif entry.has_suggestion:
        entry.status = "SUGGESTION"
    else:
        entry.status = "OK"


def load_rir_data(publishers: list[Record]) -> RIRCollection:
    """Organizes Records into a RIRCollection structure."""
    rir_map: dict[str, RIR] = {}

    for record in publishers:
        if not record.source or not record.netname:
            continue

        rir_name = record.source

        if rir_name not in rir_map:
            rir_map[rir_name] = RIR(name=rir_name)

        rir = rir_map[rir_name]
        netname_key = record.netname

        if netname_key not in rir.netnames:
            rir.netnames[netname_key] = Netname(name=netname_key)

        rir.netnames[netname_key].records.append(ValidatorRecord(
            record=record,
            report_url="",
        ))

    return RIRCollection(rirs=rir_map)


def _sanitize(s: str) -> str:
    """Removes unsafe filesystem characters."""
    s = s.strip()
    return re.sub(r"[^a-zA-Z0-9\-_]+", "", s)


def get_source_table_path(source: str) -> str:
    if source:
        return _sanitize(source).lower()
    return ""


def get_netname_table_path(netname: str) -> str:
    if netname:
        return _sanitize(netname)
    return ""


def validate_ip_prefix(entry: Entry):
    """Validates the IP prefix format and properties."""
    if not entry.ip_prefix:
        entry.add_status_message(ERR_IP_PREFIX_EMPTY)
        return

    try:
        network = ipaddress.ip_network(entry.ip_prefix, strict=False)
    except ValueError:
        entry.add_status_message(ERR_IP_PREFIX_INVALID)
        return

    entry.ip_prefix = str(network)

    if isinstance(network, ipaddress.IPv4Network):
        entry.ip_version = "IPv4"
    else:
        entry.ip_version = "IPv6"

    if is_private_address(network.network_address):
        entry.add_status_message(ERR_IP_PREFIX_NON_PUBLIC)
        return

    if entry.ip_version == "IPv4":
        if network.prefixlen < 22:
            entry.add_status_message(SUGGEST_IPV4_PREFIX_LARGE)
    else:
        if network.prefixlen < 64:
            entry.add_status_message(SUGGEST_IPV6_PREFIX_LARGE)


def is_private_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks if an IP is private or reserved."""
    if ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        for net in _IPV4_PRIVATE_RANGES:
            if ip in net:
                return True
    else:
        for net in _IPV6_PRIVATE_RANGES:
            if ip in net:
                return True

    return False


def validate_country_code(entry: Entry, ctx: ValidationContext):
    """Validates the ISO 3166-1 country code."""
    if not entry.country_code:
        return
    if entry.country_code not in ctx.countries:
        entry.add_status_message(ERR_COUNTRY_CODE_INVALID)


def validate_region_code(entry: Entry, ctx: ValidationContext):
    """Validates the ISO 3166-2 region code."""
    if not entry.region_code:
        return

    region_pattern = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")
    if not region_pattern.match(entry.region_code):
        entry.add_status_message(ERR_REGION_CODE_FORMAT)
        return

    if entry.region_code not in ctx.regions:
        entry.add_status_message(ERR_REGION_CODE_INVALID)
        return

    if entry.country_code:
        region_country = entry.region_code.split("-")[0]
        if region_country != entry.country_code:
            entry.add_status_message(ERR_REGION_CODE_MISMATCH)


def validate_city_name(entry: Entry, ctx: ValidationContext):
    """Validates the city name for inconsistencies."""
    if not entry.city:
        return

    city_lower = entry.city.strip().lower()

    for placeholder in PLACEHOLDER_VALUES:
        if city_lower == placeholder:
            entry.add_status_message(ERR_CITY_PLACEHOLDER)
            return

    for abbrev in ABBREVIATED_VALUES:
        if city_lower == abbrev:
            entry.add_status_message(ERR_CITY_ABBREVIATED)
            return

    if ("  " in entry.city or
            (entry.city.upper() == entry.city and len(entry.city) > 3) or
            re.search(r"[A-Z][a-z]+[A-Z]", entry.city)):
        entry.add_status_message(WARN_CITY_FORMATTING_BAD)


def validate_postal_code(entry: Entry):
    """Checks that postal codes are not included (deprecated by RFC 8805)."""
    if entry.postal_code:
        entry.add_status_message(ERR_POSTAL_CODE_DEPRECATED)


def provide_tuning_recommendations(entry: Entry, ctx: ValidationContext):
    """Provides suggestions for optimizing geofeed entries."""
    is_small_territory = ctx.small_territories.get(entry.country_code, False)

    if is_small_territory and entry.region_code:
        entry.add_status_message(SUGGEST_REGION_UNNECESSARY_SMALL_TERRITORY)

    if is_small_territory and entry.city:
        entry.add_status_message(SUGGEST_CITY_UNNECESSARY_SMALL_TERRITORY)

    if not is_small_territory and entry.city and not entry.region_code:
        entry.add_status_message(SUGGEST_REGION_RECOMMENDED_WITH_CITY)

    if not entry.country_code and not entry.region_code and not entry.city:
        entry.add_status_message(SUGGEST_CONFIRM_DO_NOT_GEOLOCATE)
        entry.do_not_geolocate = True


def check_for_issues(country_code: str, region_code: str, ctx: ValidationContext) -> bool:
    """Checks if country/region codes have issues."""
    if country_code and country_code not in ctx.countries:
        return True
    if region_code and region_code not in ctx.regions:
        return True
    return False
