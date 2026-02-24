# IP Geofeed Validator

A modular Go application for validating RFC 8805-compliant IP geolocation feeds. The validator checks CSV-formatted geofeed data for syntax errors, consistency issues, and provides tuning recommendations.

## Features

- **IP Prefix Validation**: Validates CIDR notation and checks for private/reserved ranges
- **Country Code Validation**: Verifies ISO 3166-1 alpha-2 compliance
- **Region Code Validation**: Validates ISO 3166-2 subdivision codes
- **City Name Validation**: Detects placeholder values and formatting inconsistencies
- **Postal Code Checking**: Enforces RFC 8805 privacy requirements
- **Tuning Recommendations**: Suggests optimization improvements for geofeed entries
- **HTML Report Generation**: Creates detailed validation reports with error categorization
- **URL Support**: Download and validate geofeed files directly from URLs
- **Structured Error Codes**: Unique error IDs for each validation issue (1xxx = errors, 2xxx = warnings, 3xxx = suggestions)

## Project Structure

```
ip-geofeed/
├── main.go                              # Entry point
├── go.mod                               # Go module definition
├── go.sum                               # Module checksums
├── run/                                 # Downloaded data from URLs (gitignored)
├── internal/
│   ├── parser/
│   │   └── parser.go                   # CSV parsing and URL downloading
│   │
│   ├── geofeed_validation/
│   │   ├── validator.go                # Core validation logic
│   │   ├── tuner.go                    # Tuning recommendations
│   │   ├── errors.go                   # Structured error definitions
│   │   ├── iso3166-1.json              # Country codes data
│   │   ├── iso3166-2.json              # Region codes data
│   │   └── small-territories.json      # Small territories list
│   │
│   └── html_template/
│       ├── html.go                     # HTML report generation
│       └── entries.html                # HTML template
│
├── testdata/
│   └── sample_geofeed.csv              # Sample test data
│
└── README.md                           # This file
```

## Prerequisites

- Go 1.21 or later

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

### Basic Usage

The validator accepts both local file paths and URLs:

```bash
# Local file
./geofeed-validator path/to/geofeed.csv

# URL (automatically downloads to run/data directory)
./geofeed-validator https://example.com/geofeed.csv
```

The validator will:
1. Parse the CSV file (or download from URL if needed)
2. Load validation data (ISO codes, territories)
3. Validate each entry against RFC 8805 rules
4. Generate an HTML report named `report.html`

### Input File Format

The CSV file should follow RFC 8805 format with 4-5 columns:

```
IP Prefix, Country Code, Region Code, City[, Postal Code (deprecated)]
```

**Example CSV:**
```csv
# Sample geofeed entries
1.2.3.0/24,US,US-CA,San Francisco
2.3.4.0/24,GB,GB-LND,London
3.4.5.0/24,FR,FR-75,Paris
```

**Important Notes:**
- Lines starting with `#` are treated as comments and skipped
- Empty lines are ignored
- IP prefixes must be in valid CIDR notation
- Country codes must be ISO 3166-1 alpha-2 format (e.g., US, GB, FR)
- Region codes must be ISO 3166-2 format: `COUNTRY-SUBDIVISION` (e.g., US-CA, GB-LND)
- Postal codes are deprecated and will trigger validation errors
- Only rows with exactly 4 or 5 columns are processed

## Output

The validator generates an HTML report (`report.html`) with:

- **Error entries**: Critical issues that must be fixed
- **Warning entries**: Potential issues that should be reviewed
- **Suggestion entries**: Optimization recommendations
- **OK entries**: Valid entries with no issues

Each entry displays:
- Line number from the original CSV
- IP prefix
- Geolocation data (country, region, city)
- Detailed validation messages with unique error IDs
