# IP Geofeed Validator & Tuner

A  Go application for validating, analyzing, and tuning RFC 8805-compliant IP geolocation feeds. The tool performs comprehensive validation checks, provides intelligent tuning recommendations, and generates detailed HTML reports with actionable insights.

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
- **Interactive HTML Reports**: Beautiful, filterable reports with categorized validation issues
- **Metadata Statistics**: Comprehensive summary including accuracy levels, IP versions, and error counts
- **Structured Error Codes**: Unique identifiers for each validation issue (1xxx = errors, 2xxx = warnings, 3xxx = suggestions)

### Operational Modes
- **Single File Mode**: Validate individual CSV files or URLs
- **Bulk Validation Mode**: Process multiple geofeeds from a JSON manifest with publisher metadata
- **URL Support**: Automatically download and validate remote geofeed files
- **Organized Output**: Generates hierarchical report structure based on publisher/organization metadata


## Prerequisites

- Go 1.21 or later
- Internet connection (for URL downloads and tuning API)

## Installation

### Building from Source

```bash
cd experimental/ip-geofeed
go build -o geofeed-validator main.go
```

### Initialize Go Module

If this is a fresh clone:

```bash
go mod init ip-geofeed
go mod tidy
```

## Usage

### Single File Validation

Validate a single geofeed file from a local path or URL:

```bash
# Local file
./geofeed-validator path/to/geofeed.csv

# Remote URL (automatically downloads to run/data/)
./geofeed-validator https://example.com/geofeed.csv
```


### Bulk Validation Mode

Process multiple geofeeds from a JSON manifest containing publisher metadata:

```bash
./geofeed-validator --bulk run/data/publishers.json
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
- Reports are organized by source/org/netname/inetnum in `run/output/`
- Downloads are cached in `run/data/`


### Input File Format

Geofeed CSV files must follow RFC 8805 format with 4-5 columns:

```
IP Prefix, Country Code, Region Code, City[, Postal Code]
```

**Example CSV:**
```csv
# Sample geofeed entries
1.2.3.0/24,US,US-CA,San Francisco
2.3.4.0/24,GB,GB-LND,London
3.4.5.0/24,FR,FR-75,Paris

# Do-not-geolocate entry (all location fields empty)
4.5.6.0/24,,,

# Country-level accuracy only
5.6.7.0/24,DE,,
```

## Output & Reports

### HTML Report Structure

Generated reports include:

**Summary Metadata:**
- Total entries, IPv4/IPv6 breakdown, invalid entries count
- Error/Warning/Suggestion/OK category totals
- Accuracy levels (city-level, region-level, country-level, do-not-geolocate)
- Timestamp and input file information

**Entry Details:**
- Line number from original CSV
- IP prefix with version indicator
- Location data (country, region, city)
- Status badge (ERROR/WARNING/SUGGESTION/OK)
- Validation messages with unique error codes
- Tuning recommendations with geocoded values

## Development

### Debugging with VS Code

The project includes launch configurations in `.vscode/launch.json`:

1. **Debug Go Program (single geofeed)** - Uses `testdata/sample_geofeed.csv`
2. **Debug Go Program (custom input)** - Prompts for file path or URL
3. **Debug Go Program (bulk mode)** - Uses `run/data/geofeeds.csv`
4. **Debug Go Program (bulk mode - custom)** - Prompts for publishers file
