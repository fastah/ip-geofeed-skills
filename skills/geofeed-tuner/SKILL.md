---
name: geofeed-tuner
description: >
  Use this skill whenever the user mentions IP geolocation feeds, RFC 8805, geofeeds, inetnum,
  inet6num, CIDR subnets, or wants help creating, tuning, validating, or publishing a
  self-published IP geolocation feed in CSV format. Also trigger when the user is a network
  operator, ISP, mobile carrier, cloud provider, hosting company, IXP, or satellite provider
  asking about IP geolocation accuracy, prefix mapping, or WHOIS geofeed attributes.
  Helps create, refine, and improve CSV-format IP geolocation feeds with opinionated
  recommendations beyond RFC 8805 compliance. Do NOT use for private or internal IP address
  management — applies only to publicly routable IP addresses.
license: Apache-2.0
metadata:
  author: Sid Mathur <support@getfastah.com>
  version: "0.4"
compatibility: Requires Python 3
---

# Geofeed Tuner – Create Better IP Geolocation Feeds

This skill helps you create and improve IP geolocation feeds in CSV format by:
- Ensuring your CSV is well-formed and consistent
- Checking alignment with [RFC 8805](references/rfc8805.txt) (the industry standard)
- Applying **opinionated best practices** learned from real-world deployments
- Suggesting improvements for accuracy, completeness, and privacy

## When to Use This Skill

- Use this skill when a user asks for help **creating, improving, or publishing** an IP geolocation feed file in CSV format.
- Use it to **tune and troubleshoot CSV geolocation feeds** — catching errors, suggesting improvements, and ensuring real-world usability beyond RFC compliance.
- **Intended audience:**
  - Network operators, administrators, and engineers responsible for publicly routable IP address space
  - Organizations such as ISPs, mobile carriers, cloud providers, hosting and colocation companies, Internet Exchange operators, and satellite internet providers
- **Do not use** this skill for private or internal IP address management; it applies **only to publicly routable IP addresses**.

## Prerequisites

- **Python 3** is required.

## Directory Structure and File Management

This skill uses a clear separation between **distribution files** (read-only) and **working files** (generated at runtime).

### Read-Only Directories (Do Not Modify)

The following directories contain static distribution assets. **Do not create, modify, or delete files in these directories:**

| Directory      | Purpose                                                    |
|----------------|------------------------------------------------------------|
| `assets/`      | Static data files (ISO codes, examples)                    |
| `references/`  | RFC specifications and code snippets for reference         |
| `scripts/`     | Executable code and HTML template files for reports        |

### Working Directories (Generated Content)

All generated, temporary, and output files go in these directories:

| Directory       | Purpose                                              |
|-----------------|------------------------------------------------------|
| `run/`          | Working directory for all agent-generated content    |
| `run/data/`     | Downloaded CSV files from remote URLs                |
| `run/report/`   | Generated HTML tuning reports                        |

### File Management Rules

1. **Never write to `assets/`, `references/`, or `scripts/`** — these are part of the skill distribution and must remain unchanged.
2. **All downloaded input files** (from remote URLs) must be saved to `./run/data/`.
3. **All generated HTML reports** must be saved to `./run/report/`.
4. **All generated Python scripts** must be saved to `./run/`.
5. The `run/` directory may be cleared between sessions; do not store permanent data there.


## Processing Pipeline: Sequential Phase Execution

All phases must be executed **in order**, from Phase 1 through Phase 6. Each phase depends on the successful completion of the previous phase. For example, **structure checks** must complete before **quality analysis** can run.

The phases are summarized below. The agent must follow the detailed steps outlined further in each phase section.

| Phase | Name                       | Description                                                                       |
|-------|----------------------------|-----------------------------------------------------------------------------------|
| 1     | Understand the Standard    | Review the key requirements of RFC 8805 for self-published IP geolocation feeds   |
| 2     | Gather Input               | Collect IP subnet data from local files or remote URLs                            |
| 3     | Checks & Suggestions       | Validate CSV structure, analyze IP prefixes, and check data quality               |
| 4     | Tuning Data Lookup         | Use Fastah's MCP tool to retrieve tuning data for improving geolocation accuracy  |
| 5     | Generate Tuning Report     | Create an HTML report summarizing the analysis and suggestions                    |
| 6     | Final Review               | Verify consistency and completeness of the report data                            |

**Do not skip phases.** Each phase provides critical checks or data transformations required by subsequent stages.


### Execution Plan Rules

Before executing each phase, the agent MUST generate a visible TODO checklist.

The plan MUST:
- Appear at the very start of the phase
- List every step in order
- Use a checkbox format
- Be updated live as steps complete


### Phase 1: Understand the Standard

The key requirements from RFC 8805 that this skill enforces are summarized below. **Use this summary as your working reference.** Only consult the full [RFC 8805 text](references/rfc8805.txt) for edge cases, ambiguous situations, or when the user asks a standards question not covered here.

#### RFC 8805 Key Facts

**Purpose:** A self-published IP geolocation feed lets network operators publish authoritative location data for their IP address space in a simple CSV format, allowing geolocation providers to incorporate operator-supplied corrections.

**CSV Column Order (Sections 2.1.1.1–2.1.1.5):**

| Column | Field         | Required | Notes                                                      |
|--------|---------------|----------|------------------------------------------------------------|
| 1      | `ip_prefix`   | Yes      | CIDR notation; IPv4 or IPv6; must be a network address     |
| 2      | `alpha2code`  | No       | ISO 3166-1 alpha-2 country code; empty = do-not-geolocate |
| 3      | `region`      | No       | ISO 3166-2 subdivision code (e.g., `US-CA`)               |
| 4      | `city`        | No       | Free-text city name; no authoritative validation set       |
| 5      | `postal_code` | No       | **Deprecated** — must be left empty or absent             |

**Structural rules:**
- Files may contain comment lines beginning with `#` (including the header, if present).
- A header row is optional; if present, it is treated as a comment if it starts with `#`.
- Files must be encoded in UTF-8.
- Subnet host bits must not be set (i.e., `192.168.1.1/24` is invalid; use `192.168.1.0/24`).
- Applies only to **globally routable** unicast addresses — not private, loopback, link-local, or multicast space.

**Do-not-geolocate:** An entry with an empty `alpha2code` (and empty region/city) is an explicit signal that the operator does not want geolocation applied to that prefix.

**Postal codes deprecated (Section 2.1.1.5):** The fifth column must not contain postal or ZIP codes. They are too fine-grained for IP-range mapping and raise privacy concerns.


### Phase 2: Gather Input

- If the user has not already provided a list of IP subnets or ranges (sometimes referred to as `inetnum` or `inet6num`), prompt them to supply it. Accepted input formats:
  - Text pasted into the chat
  - A local CSV file
  - A remote URL pointing to a CSV file

- If the input is a **remote URL**:
  - Attempt to download the CSV file to `./run/data/` before processing.
  - On HTTP error (4xx, 5xx, timeout, or redirect loop), **stop immediately** and report to the user:
    `Feed URL is not reachable: HTTP {status_code}. Please verify the URL is publicly accessible.`
  - Do not proceed to Phase 3 with an incomplete or empty download.

- If the input is a **local file**, process it directly without downloading.

- **Encoding detection and normalization:**
  1. Attempt to read the file as UTF-8 first.
  2. If a `UnicodeDecodeError` is raised, try `utf-8-sig` (UTF-8 with BOM), then `latin-1`.
  3. Once successfully decoded, re-encode and write the working copy as UTF-8.
  4. If no encoding succeeds, stop and report: `Unable to decode input file. Please save it as UTF-8 and try again.`


### Phase 3: Checks & Suggestions

#### Execution Rules
- Generate **exactly one script** for this phase.
- Do NOT combine this phase with others.
- Do NOT precompute future-phase data.
- Store the output as a JSON file at: [`./run/data/report-data.json`](./run/data/report-data.json)

#### Schema Definition

The JSON structure below is **IMMUTABLE**.

```json
{
  "input_file": "",
  "timestamp": "",

  "total_entries": 0,
  "ipv4_entries": 0,
  "ipv6_entries": 0,
  "invalid_entries": 0,

  "error_count": 0,
  "warning_count": 0,
  "ok_count": 0,
  "suggestion_count": 0,

  "city_level_accuracy": 0,
  "region_level_accuracy": 0,
  "country_level_accuracy": 0,
  "do_not_geolocate_entries": 0,

  "entries": [
    {
      "line": 0,
      "ip_prefix": "",
      "country": "",
      "region": "",
      "city": "",

      "status": "",

      "messages": [
        {
          "status": "",
          "message": ""
        }
      ],

      "has_error": false,
      "has_warning": false,
      "has_suggestion": false,
      "need_region": false,
      "is_small_territory": false
    }
  ]
}
```

Field definitions:
- `input_file`: The original input source, either a local filename or a remote URL.
- `timestamp`: Milliseconds since Unix epoch when the tuning was performed.
- `total_entries`: Total number of data rows processed (excluding comment and blank lines).
- `ipv4_entries`: Count of entries that are IPv4 subnets.
- `ipv6_entries`: Count of entries that are IPv6 subnets.
- `invalid_entries`: Count of entries that failed IP prefix parsing.
- `error_count`: Total entries whose `status` is `ERROR`.
- `warning_count`: Total entries whose `status` is `WARNING`.
- `ok_count`: Total entries whose `status` is `OK`.
- `suggestion_count`: Total entries whose `status` is `SUGGESTION`.
- `city_level_accuracy`: Count of valid entries where `city` is non-empty.
- `region_level_accuracy`: Count of valid entries where `region` is non-empty and `city` is empty.
- `country_level_accuracy`: Count of valid entries where `country` is non-empty, `region` is empty, and `city` is empty.
- `do_not_geolocate_entries`: Count of valid entries where `country`, `region`, and `city` are all empty.
- `entries`: Array of objects, one per data row, with the following per-entry fields:
  - `line`: 1-based line number in the original CSV (counting all lines including comments and blanks).
  - `ip_prefix`: The normalized IP prefix in CIDR slash notation.
  - `country`: The ISO 3166-1 alpha-2 country code, or empty string.
  - `region`: The ISO 3166-2 region code (e.g., `US-CA`), or empty string.
  - `city`: The city name, or empty string.
  - `status`: Highest severity assigned: `ERROR` > `WARNING` > `SUGGESTION` > `OK`.
  - `messages`: Array of `{ "status": "...", "message": "..." }` validation messages.
  - `has_error`: `true` if any message has status `ERROR`.
  - `has_warning`: `true` if any message has status `WARNING`.
  - `has_suggestion`: `true` if any message has status `SUGGESTION`.
  - `need_region`: `true` if the entry triggered the "missing region when city is specified" suggestion.
  - `is_small_territory`: `true` if the country is classified as a small territory per `assets/small-territories.json`.

#### Accuracy Level Counting Rules

Accuracy levels are **mutually exclusive**. Assign each valid (non-ERROR, non-invalid) entry to exactly one bucket based on the most granular non-empty geo field:

| Condition                                       | Bucket                     |
|-------------------------------------------------|----------------------------|
| `city` is non-empty                             | `city_level_accuracy`      |
| `region` non-empty AND `city` is empty          | `region_level_accuracy`    |
| `country` non-empty, `region` and `city` empty  | `country_level_accuracy`   |
| All three fields (`country`, `region`, `city`) empty | `do_not_geolocate_entries` |

**Do not count** entries with `has_error: true` or entries in `invalid_entries` in any accuracy bucket.

The agent MUST NOT:
- Rename fields
- Add or remove fields
- Change data types
- Reorder keys
- Alter nesting
- Wrap the object
- Split into multiple files

If a value is unknown, **leave it empty** — never invent data.

#### Structure & Format Check

This phase verifies that your feed is well-formed and parseable. **Critical structural errors** must be resolved before the tuner can analyze geolocation quality.

##### CSV Structure

This subsection defines rules for **CSV-formatted input files** used for IP geolocation feeds.
The goal is to ensure the file can be parsed reliably and normalized into a **consistent internal representation**.

- **CSV Structure Checks**
  - If `pandas` is available, use it for CSV parsing.
  - Otherwise, fall back to Python's built-in `csv` module.

  - Ensure the CSV contains **exactly 4 or 5 logical columns**.
  - Comment lines are allowed.
  - A header row **may or may not** be present.
  - If no header row exists, assume the implicit column order:
    ```
    ip_prefix, alpha2code, region, city, postal code (deprecated)
    ```
  - Refer to the example input file:
    [`assets/example/01-user-input-rfc8805-feed.csv`](assets/example/01-user-input-rfc8805-feed.csv)

- **CSV Cleansing and Normalization**
  - Clean and normalize the CSV using Python logic equivalent to the following operations:
    - Select only the **first five columns**, dropping any columns beyond the fifth.
    - Write the output file with a **UTF-8 BOM**.

  - **Comments**
    - Remove comment rows where the **first column begins with `#`**.
    - This also removes a header row if it begins with `#`.
    - Create a map of comments using the **1-based line number** as the key and the full original line as the value. Also store blank lines.
    - Store this map in a JSON file at: [`./run/data/comments.json`](./run/data/comments.json)
    - Example: `{ "4": "# It's OK for small city states to leave state ISO2 code unspecified" }`

- **Notes**
  - Both implementation paths (`pandas` and built-in `csv`) must write output using
    the `utf-8-sig` encoding to ensure a **UTF-8 BOM** is present.

#### IP Prefix Analysis
  - Check that the `ip_prefix` field is present and non-empty for each entry.
  - Check for duplicate `ip_prefix` values across entries.
  - If duplicates are found, stop the skill and report to the user with the message: `Duplicate IP prefix detected: {ip_prefix_value} appears on lines {line_numbers}`
  - If no duplicates are found, continue with the analysis.

  - **Checks**
    - Each subnet must parse cleanly as either an **IPv4 or IPv6 network** using the code snippets in the `references/` folder.
    - Subnets must be normalized and displayed in **CIDR slash notation**.
      - Single-host IPv4 subnets must be represented as **`/32`**.
      - Single-host IPv6 subnets must be represented as **`/128`**.

  - **ERROR**
    - Report the following conditions as **ERROR**:

    - **Invalid subnet syntax**
      - Message: `Invalid IP prefix: unable to parse as IPv4 or IPv6 network`

    - **Non-public address space**
      - Applies to subnets that are **private, loopback, link-local, multicast, or otherwise non-public**
        - In Python, detect non-public ranges using `is_private` and related address properties as shown in `./references`.
      - Message: `Non-public IP range is not allowed in an RFC 8805 feed`

    - **RFC 8805–incompatible subnet**
      - Any subnet failing mandatory RFC 8805 constraints
      - Message: `Subnet is not valid for publication in an RFC 8805 geofeed`

  - **SUGGESTION**
    - Report the following conditions as **SUGGESTION**:

    - **Overly large IPv6 subnets**
      - Prefixes shorter than `/64`
      - Message: `IPv6 prefix is unusually large and may indicate a typo`

    - **Overly large IPv4 subnets**
      - Prefixes shorter than `/22`
      - Message: `IPv4 prefix is unusually large and may indicate a typo`

#### Geolocation Quality Check

Analyze the **accuracy and consistency** of geolocation data:
  - Country codes
  - Region codes
  - City names
  - Deprecated fields

This phase runs after structural checks pass.

##### Country Code Analysis
  - Use the locally available data table [`ISO3166-1`](assets/iso3166-1.json) for checking.
    - JSON array of countries and territories with ISO codes
    - Each object includes:
      - `alpha_2`: two-letter country code
      - `name`: short country name
      - `flag`: flag emoji
    - This file represents the **superset of valid `alpha2code` values** for an RFC 8805 CSV.
  - Check `alpha2code` (RFC 8805 Section 2.1.1.2) against the `alpha_2` attribute.
  - Sample code is available in the `references/` directory.

  - If a country is found in [`assets/small-territories.json`](assets/small-territories.json), set `is_small_territory` to `true`. This value is used in later checks and suggestions related to small territories.

  - **ERROR**
    - Report the following conditions as **ERROR**:
    - **Invalid country code**
      - Condition: `alpha2code` is present but not found in the `alpha_2` set
      - Message: `Invalid country code: not a valid ISO 3166-1 alpha-2 value`

##### Region Code Analysis
  - Use the locally available data table [`ISO3166-2`](assets/iso3166-2.json) for checking.
    - JSON array of country subdivisions with ISO-assigned codes
    - Each object includes:
      - `code`: subdivision code prefixed with country code (e.g., `US-CA`)
      - `name`: short subdivision name
    - This file represents the **superset of valid `region` values** for an RFC 8805 CSV.
  - If a `region` value is provided (RFC 8805 Section 2.1.1.3):
    - Check that the format matches `{COUNTRY}-{SUBDIVISION}` (e.g., `US-CA`, `AU-NSW`).
    - Check the value against the `code` attribute (already prefixed with the country code).

  - **Small-territory exception:** If `is_small_territory` is `true` **and** the `region` value equals the entry's `alpha2code` (e.g., `SG` as both country and region for Singapore), treat the region as acceptable — skip all region validation checks for this entry. Small territories are effectively city-states with no meaningful ISO 3166-2 administrative subdivisions.

  - **ERROR**
    - Report the following conditions as **ERROR**:
    - **Invalid region format**
      - Condition: `region` does not match `{COUNTRY}-{SUBDIVISION}` **and** the small-territory exception does not apply
      - Message: `Invalid region format; expected COUNTRY-SUBDIVISION (e.g., US-CA)`
    - **Unknown region code**
      - Condition: `region` value is not found in the `code` set **and** the small-territory exception does not apply
      - Message: `Invalid region code: not a valid ISO 3166-2 subdivision`
    - **Country–region mismatch**
      - Condition: Country portion of `region` does not match `alpha2code`
      - Message: `Region code does not match the specified country code`

##### City Name Analysis

  - City names are validated using **heuristic checks only**.
  - There is currently **no authoritative dataset** available for validating city names.

  - **ERROR**
    - Report the following conditions as **ERROR**:
    - **Placeholder or non-meaningful values**
      - Condition: Placeholder or non-meaningful values including but not limited to:
        - `undefined`
        - `Please select`
        - `null`
        - `N/A`
        - `TBD`
        - `unknown`
      - Message: `Invalid city name: placeholder value is not allowed`

    - **Truncated names, abbreviations, or airport codes**
      - Condition: Truncated names, abbreviations, or airport codes that do not represent valid city names:
        - `LA`
        - `Frft`
        - `sin01`
        - `LHR`
        - `SIN`
        - `MAA`
      - Message: `Invalid city name: abbreviated or code-based value detected`

  - **WARNING**
    - Report the following conditions as **WARNING**:
    - **Inconsistent casing or formatting**
      - Condition: City names with inconsistent casing, spacing, or formatting that may reduce data quality, for example:
        - `HongKong` vs `Hong Kong`
        - Mixed casing or unexpected script usage
      - Message: `City name formatting is inconsistent; consider normalizing the value`

##### Postal Code Check
  - RFC 8805 Section 2.1.1.5 explicitly **deprecates postal or ZIP codes**.
  - Postal codes can represent very small populations and are **not considered privacy-safe** for mapping IP address ranges, which are statistical in nature.

  - **ERROR**
    - Report the following conditions as **ERROR**:
    - **Postal code present**
      - Condition: A non-empty value is present in the postal/ZIP code field.
      - Message: `Postal codes are deprecated by RFC 8805 and must be removed for privacy reasons`

#### Tuning & Recommendations

This phase applies **opinionated recommendations** beyond RFC 8805, learned from real-world geofeed deployments, that improve accuracy and usability.

- **SUGGESTION**
  - Report the following conditions as **SUGGESTION**:

  - **Region or city specified for small territory**
    - Condition:
      - `is_small_territory` is `true`
      - `region` is non-empty **OR**
      - `city` is non-empty.
    - Message: `Region or City-level granularity is usually unnecessary for small territories; consider removing the region and city values`

  - **Missing region code when city is specified**
    - Condition:
      - `city` is non-empty
      - `region` is empty
      - `is_small_territory` is `false`
    - Action: Set `need_region = true`
    - Message: `Region code is recommended when a city is specified; consider adding the appropriate region code for better accuracy`

  - **Unspecified geolocation for subnet**
    - Condition: All geographical fields (`alpha2code`, `region`, `city`) are empty for a subnet.
    - Message: `Confirm whether this subnet is intentionally marked as do-not-geolocate or missing location data`


### Phase 4: Tuning Data Lookup

#### Objective
Lookup all the entries in the file using Fastah's `rfc8805-row-place-search` tool.

#### Execution Rules
- Use a **separate script** _only_ for payload generation (read the dataset and write one or more payload JSON files; do not call MCP from this script).
- Server only accepts 1000 entries per request, so if there are more than 1000 entries, split into multiple requests.
- The agent must read the generated payload files, construct the requests from them, and send those requests to the MCP server in batches of at most 1000 entries each.
- **On MCP failure:** If the MCP server is unreachable, returns an error, or returns no results for any batch, log a warning and continue to Phase 5. Set `tuned_entries: []` for all affected entries. Do not block report generation. Notify the user clearly: `Tuning data lookup unavailable; the report will show validation results only.`
- Suggestions are **advisory only** — **never auto-populate** them.

#### Step 1: Load Dataset
Load the dataset from: [./run/data/report-data.json](./run/data/report-data.json)
- Read the `entries` array.
- Include all entries.

#### Step 2: Build Lookup Payload with Deduplication

Reduce server requests by deduplicating identical entries:
- For each entry in `entries`, compute a content hash (hash of countryCode + regionCode + cityName).
- Create a deduplication map: `{ contentHash -> { rowKey, payload, entryIndices: [] } }`. rowKey is a UUID that will be sent to the MCP server for matching responses.
- If an entry's hash already exists, append its **0-based array index** in `entries` to that deduplication entry's `entryIndices` array.
- If hash is new, generate a **UUID (rowKey)** and create a new deduplication entry.

Build request batches:
- Extract unique deduplicated entries from the map, keeping them in deduplication order.
- Build request batches of up to 1000 items each.
- For each batch, keep an in-memory structure like `[{ rowKey, payload, entryIndices }, ...]` to match responses back by rowKey.
- When writing the MCP payload file, include the `rowKey` field with each payload object:

```json
[
    {"rowKey": "550e8400-e29b-41d4-a716-446655440000", "countryCode":"CA","regionCode":"CA-ON","cityName":"Toronto"},
    {"rowKey": "6ba7b810-9dad-11d1-80b4-00c04fd430c8", "countryCode":"IN","regionCode":"IN-KA","cityName":"Bangalore"},
    {"rowKey": "6ba7b811-9dad-11d1-80b4-00c04fd430c8", "countryCode":"IN","regionCode":"IN-KA"}
]
```

- When reading responses, match each response `rowKey` field to the corresponding deduplication entry to retrieve all associated `entryIndices`.

Rules:
- Write payload to: [./run/data/mcp-server-payload.json](./run/data/mcp-server-payload.json)
- Exit the script after writing the payload.

#### Step 3: Invoke Fastah MCP Tool

- Server: `https://mcp.fastah.ai/mcp`
- Tool: `rfc8805-row-place-search`
- Open [./run/data/mcp-server-payload.json](./run/data/mcp-server-payload.json) and send all deduplicated entries with their rowKeys.
- If there are more than 1000 deduplicated entries after deduplication, split into multiple requests of 1000 entries each.
- The server will respond with the same `rowKey` field in each response for mapping back.
- Do NOT use local data.

#### Step 4: Attach Tuned Data to Entries

- Use a **separate script** for attaching tuned data.
- Load both [./run/data/report-data.json](./run/data/report-data.json) and the deduplication map (held in memory from Step 2, or re-derived from the payload file).
- For each response from the MCP server:
  - Extract the `rowKey` from the response.
  - Look up the `entryIndices` array associated with that `rowKey` from the deduplication map.
  - For each index in `entryIndices`, attach the normalized suggestions to `entries[index]`.
- Keep **at least three suggestions** when available.
- If fewer than three exist, keep all returned values.

Create the field on each affected entry if it does not exist:

```json
"tuned_entries": [
  {
    "placeName": "",
    "countryCode": "",
    "regionCode": "",
    "placeType": "",
    "h3Cells": [],
    "boundingBox": []
  }
]
```

Entries with no UUID match (i.e. the MCP server returned no response for their UUID) must receive an empty `tuned_entries: []` array — never leave the field absent.

#### Step 5: Store Updated Dataset

- Write the dataset back to: [./run/data/report-data.json](./run/data/report-data.json)
- Rules:
  - Maintain all existing validation flags.
  - Do NOT create additional intermediate files.


### Phase 5: Generate Tuning Report

Generate a **self-contained HTML report** by injecting data from `./run/data/report-data.json` and `./run/data/comments.json` into the template at `./scripts/templates/index.html`.

Write the completed report to `./run/report/geofeed-report.html`. After generating, open it in the system's default browser.

**Do not hand-write HTML for individual rows.** Write a Python script that reads the data files and produces the final HTML. Do not modify any CSS, JavaScript, or structural HTML in the template outside the injection points described below.

#### Step 1: Inject Summary Metadata

Replace the hardcoded values in the following elements by string substitution. All values come from `report-data.json` top-level fields:

| Element (by `id`)        | Source field            | Notes                                                         |
|--------------------------|-------------------------|---------------------------------------------------------------|
| `#inputFileMetrics`      | `input_file`            | Replace inner text of the `<span>`                           |
| timestamp `<script>`     | `timestamp`             | Replace only the integer `1773720806552` with the actual value|
| `#totalEntriesMetrics`   | `total_entries`         | Replace inner text of the `<span>`                           |
| `#ipv4EntriesMetrics`    | `ipv4_entries`          | Replace inner text of the `<span>`                           |
| `#ipv6EntriesMetrics`    | `ipv6_entries`          | Replace inner text of the `<span>`                           |
| `#invalidEntriesMetrics` | `invalid_entries`       | Replace inner text of the `<span>`                           |
| `#errorCountMetrics`     | `error_count`           | Replace inner text of the `<span>`                           |
| `#warningCountMetrics`   | `warning_count`         | Replace inner text of the `<span>`                           |
| `#suggestionsMetrics`    | `suggestion_count`      | Replace inner text of the `<span>`                           |
| `#okCountMetrics`        | `ok_count`              | Replace inner text of the `<span>`                           |
| `#cityAccuracy`          | `city_level_accuracy`   | Replace inner text of the `<span>`                           |
| `#regionAccuracy`        | `region_level_accuracy` | Replace inner text of the `<span>`                           |
| `#countryAccuracy`       | `country_level_accuracy`| Replace inner text of the `<span>`                           |
| `#doNotGeolocate`        | `do_not_geolocate_entries` | Replace inner text of the `<span>`                        |

The timestamp element requires special treatment. Find this exact pattern in the template and replace only the integer literal:
```html
new Date( 1773720806552 )
```
Replace with:
```html
new Date( {timestamp} )
```
where `{timestamp}` is the integer millisecond epoch value from `report-data.json`.

#### Step 2: Inject the Comment Map

Locate this exact literal string in the template:
```javascript
const commentMap = JSON.parse('{}');
```
Replace the `'{}'` portion with the serialized, single-quote-safe JSON string of the comments map loaded from `./run/data/comments.json`. The result must be syntactically valid JavaScript — escape any single quotes inside comment text:
```javascript
const commentMap = JSON.parse('{...escaped JSON string...}');
```

#### Step 3: Generate and Inject Row HTML

Replace the entire content of `<tbody id="entriesTableBody">` with generated rows. For each entry in `report-data.json`'s `entries` array, generate **three consecutive `<tr>` elements**:

**Row 1 — Data row:**
```html
<tr
 id="csv-r-{line}"
 class="expandable-row"
 data-geocoding-hint=""
 data-do-not-geolocate="{true if country+region+city all empty, else false}"
 data-has-warning="{has_warning}"
 data-has-error="{has_error}"
 data-has-suggestion="{has_suggestion}"
 data-tunable="{true if tuned_entries is non-empty, else false}"
 data-tuned-country="{tuned_entries[0].countryCode or ''}"
 data-tuned-region="{tuned_entries[0].regionCode or ''}"
 data-tuned-city="{tuned_entries[0].placeName or ''}"
 data-h3-cells="{JSON array string of tuned_entries[0].h3Cells or '[]'}"
 data-bounding-box="{JSON array string of tuned_entries[0].boundingBox or '[]'}">
    <td><input type="checkbox" class="row-checkbox" checked></td>
    <td>{line}</td>
    <td><span class="status-badge status-{status.lower()}">{status_icon}{status}</span></td>
    <td><strong>{ip_prefix}</strong></td>
    <td>{country}</td>
    <td>{region}</td>
    <td>{city}</td>
</tr>
```

Status badge icons — use exactly this markup per status:

| `status`     | CSS class on `<span>`      | Icon `<i>` markup                                         |
|--------------|----------------------------|-----------------------------------------------------------|
| `OK`         | `status-ok`                | `<i class="bi bi-check-circle-fill"></i>`                 |
| `WARNING`    | `status-warning`           | `<i class="bi bi-exclamation-triangle-fill"></i>`         |
| `ERROR`      | `status-error`             | `<i class="bi bi-x-circle-fill"></i>`                     |
| `SUGGESTION` | `status-suggestion`        | `<i class="bi bi-lightbulb-fill"></i>`                    |

`data-tunable` must be the string `"true"` only when `tuned_entries` is present and has at least one element — this is what allows the "Tune All" button to apply suggested values to the row.

**Row 2 — Previous-values row:**
```html
<tr class="expand-details-row previous-values-row">
    <td></td>
    <td></td>
    <td></td>
    <td><strong>Previous values:</strong></td>
    <td class="previous-value"><span class="default-country">{country}</span></td>
    <td class="previous-value"><span class="default-region">{region}</span></td>
    <td class="previous-value"><span class="default-city">{city}</span></td>
</tr>
```

**Row 3 — Issues row:**
```html
<tr class="expand-details-row issues-row">
    <td></td>
    <td></td>
    <td colspan="5">
        <div class="issues-header">
            <strong>Issues:</strong>
            <button class="tune-all-btn" onclick="handleTuneButtonClick(this)">Tune</button>
        </div>
        {message_lines}
    </td>
</tr>
```

For each message in the entry's `messages` array, generate one `<div>`:
```html
<div class="message-line" data-id="{line * 100 + message_index}">
    <span>{message.message}</span>
    <input type="checkbox" disabled>
</div>
```
Use `message_index` as the 0-based position of the message within the entry's `messages` list. If `messages` is empty, omit the message divs — leave only the issues header `<div>`.

#### Output Guarantees

- The report must be readable in any modern browser without extra network dependencies beyond the CDN links already in the template (`leaflet`, `h3-js`, `bootstrap-icons`, Raleway font).
- All values embedded in HTML must be **HTML-escaped** (`<`, `>`, `&`, `"`) to prevent rendering issues.
- All values embedded inside JavaScript string literals (e.g., `commentMap`) must be **JSON-string-escaped**.
- All values must be derived **only from analysis output**, not recomputed heuristically.


### Phase 6: Final Review

Perform a final verification pass using concrete, checkable assertions before presenting results to the user.

**Check 1 — Entry count integrity**
- Count non-comment, non-blank data rows in the original input CSV.
- Assert: `len(entries) in report-data.json == data_row_count`
- On failure: `Row count mismatch: input has {N} data rows but report contains {M} entries.`

**Check 2 — Summary counter integrity**
- Assert all of the following; correct any that fail before generating the report:
  - `error_count == sum(1 for e in entries if e['has_error'])`
  - `warning_count == sum(1 for e in entries if e['has_warning'] and not e['has_error'])`
  - `suggestion_count == sum(1 for e in entries if e['has_suggestion'] and not e['has_error'] and not e['has_warning'])`
  - `ok_count == sum(1 for e in entries if not e['has_error'] and not e['has_warning'] and not e['has_suggestion'])`
  - `error_count + warning_count + suggestion_count + ok_count == total_entries - invalid_entries`

**Check 3 — Accuracy bucket integrity**
- Assert: `city_level_accuracy + region_level_accuracy + country_level_accuracy + do_not_geolocate_entries == total_entries - invalid_entries`
- On failure, trace and fix the bucketing logic before proceeding.

**Check 4 — No duplicate line numbers**
- Assert: all `line` values in `entries` are unique.
- On failure, report the duplicated line numbers to the user.

**Check 5 — tuned_entries completeness**
- Assert: every object in `entries` has a `tuned_entries` key (even if its value is `[]`).
- On failure, add `"tuned_entries": []` to any entry missing the key, then re-save `report-data.json`.

**Check 6 — Report file is present and non-empty**
- Confirm `./run/report/geofeed-report.html` was written and has a file size greater than zero bytes.
- On failure, regenerate the report before presenting to the user.