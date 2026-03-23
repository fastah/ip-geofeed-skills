# IP Geofeed Validator & Tuner (Python)

A Python application for validating, analyzing, and tuning RFC 8805-compliant IP geolocation feeds. This is a Python port of the Go implementation, using Jinja2 for HTML templating.

## Features

### Validation
- **IP Prefix Validation**: Validates CIDR notation, checks for private/reserved ranges, and warns about unusually large prefixes
- **Country Code Validation**: Verifies ISO 3166-1 alpha-2 compliance
- **Region Code Validation**: Validates ISO 3166-2 subdivision codes
- **City Name Validation**: Detects placeholder values, abbreviated codes, and formatting inconsistencies
- **Postal Code Checking**: Enforces RFC 8805 privacy requirements (postal codes are deprecated)

### Intelligent Tuning
- **Geocoding API Integration**: Leverages place-search API to provide accurate location corrections
- **Smart Recommendations**: Suggests appropriate region/city values based on geocoding data

### Output & Reporting
- **Interactive HTML Reports**: Beautiful, filterable reports with categorized validation issues (rendered with Jinja2)
- **Metadata Statistics**: Comprehensive summary including accuracy levels, IP versions, and error counts
- **Structured Error Codes**: Unique identifiers for each validation issue (1xxx = errors, 2xxx = warnings, 3xxx = suggestions)

### Operational Modes
- **Single File Mode**: Validate individual CSV files or URLs
- **Bulk Validation Mode**: Process multiple geofeeds from a JSON manifest with publisher metadata
- **URL Support**: Automatically download and validate remote geofeed files
- **Organized Output**: Generates hierarchical report structure based on publisher/organization metadata

## Prerequisites

- Python 3.10 or later
- Internet connection (for URL downloads and tuning API)

## Installation

```bash
cd experimental/ip-geofeed2
pip install -r requirements.txt
```

## Usage

### Single File Validation

Validate a single geofeed file from a local path or URL:

```bash
# Local file
python3 main.py path/to/geofeed.csv

# Remote URL (automatically downloads to run/data/)
python3 main.py https://example.com/geofeed.csv

# With entry limit
python3 main.py --limit-entries 100 path/to/geofeed.csv
```

### Bulk Validation Mode

Process multiple geofeeds from a JSON manifest containing publisher metadata:

```bash
python3 main.py --bulk run/data/publishers.json
```

**Publishers JSON Format:**
```json
[
  {
    "geofeed": "https://example.com/geofeed1.csv",
    "inetnum": "1.0.0.0 - 1.0.0.255",
    "source": "RIPE",
    "netname": "EXAMPLE-NET",
    "country": "US",
    "org": "Example Org",
    "admin-c": "ADMIN-1",
    "tech-c": "TECH-1",
    "mnt-by": "EXAMPLE-MNT",
    "city": "San Francisco"
  }
]
```

In bulk mode:
- Reports are organized by source/netname/ in `run/output/`
- Downloads are cached in `run/data/`

### Using Make

```bash
make install                        # Install dependencies
make run FILE=testdata/sample-input.csv  # Single file
make run-bulk FILE=testdata/publishers.json  # Bulk mode
make clean                          # Clean output
```
