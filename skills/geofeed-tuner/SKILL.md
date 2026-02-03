---
name: geofeed-tuner
description: Helps create, refine, and improve CSV-format IP geolocation feeds with opinionated recommendations beyond RFC 8805 compliance.
license: Apache-2.0
metadata:
  author: Sid Mathur <support@getfastah.com>
  version: "0.3"
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
- Use it to **tune and troubleshoot CSV geolocation feeds** — catching errors, suggesting improvements, and ensuring real-world usability beyond just RFC compliance.
- **Intended audience**:
  - Network operators, administrators, and engineers responsible for publicly routable IP address space
  - Organizations such as ISPs, mobile carriers, cloud providers, hosting and colocation companies, Internet Exchange operators, and satellite internet providers
- **Do not use** this skill for private or internal IP address management; it applies **only to publicly routable IP addresses**.


## Prerequisite: CLI Tools and/or Languages

- **Python 3** is required.

## Directory Structure and File Management

This skill uses a clear separation between **distribution files** (read-only) and **working files** (generated at runtime).

### Read-Only Directories (Do Not Modify)

The following directories contain static distribution assets. **Do not create, modify, or delete files in these directories**:

| Directory      | Purpose                                                    |
|----------------|------------------------------------------------------------|
| `assets/`      | Static data files (ISO codes, Bootstrap CSS/JS, examples)  |
| `references/`  | RFC specifications and code snippets for reference         |
| `scripts/`     | Contains executable code that agents can run and HTML template files used as visual references for reports  |

### Working Directories (Generated Content)

All generated, temporary, and output files must be written to these directories:

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

- **MANDATORY** Read this file completely from start to finish. NEVER set any range limits when reading this file.
- All phases of the skill must be executed **in order**, from Phase 1 through Phase 7.
- Each phase depends on the successful completion of the previous phase.  
  - For example, **structure checks** must complete before **quality analysis** can run.

- Users or automation agents should **not skip phases**, as each phase provides critical checks or data transformations required for the next stage.



### Phase 1: Understand the Standard

Read Section 1 (**Introduction**) and Section 2 (**Self-Published IP Geolocation Feeds**) of the plain-text  
[RFC 8805 – A Format for Self-Published IP Geolocation Feeds](references/rfc8805.txt).

The goal of this phase is to understand the **foundation** for IP geolocation feeds, including:
- The overall purpose and scope of RFC 8805
- The required and optional data elements
- The expected syntax and semantics

This research phase establishes the conceptual foundation needed before performing any input handling or analysis in later phases.


### Phase 2: Gather Input

- If the user has not already provided a list of IP subnets or ranges (sometimes referred to as `inetnum` or `inet6num`), prompt them to supply it. The input may be provided via:
  - Text pasted into the chat
  - A local CSV file
  - A remote URL pointing to a CSV file

- If the input is a **remote URL**, download the CSV file into the `./run/data/` directory before processing.
- If the input is a **local file**, continue processing it directly without downloading.
- Normalize all input data to **UTF-8** encoding.



### Phase 3: Structure & Format Check

This phase verifies that your feed is well-formed and parseable. **Critical structural errors** must be resolved before the tuner can analyze geolocation quality.

#### CSV Structure

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
    - Optionally remove comment rows where the **first column begins with `#`**.
    - This will also remove a header row if it begins with `#`.

- **Notes**
  - Both implementation paths (`pandas` and built-in `csv`) must write output using
    the `utf-8-sig` encoding to ensure a **UTF-8 BOM** is present.

#### IP Prefix Analysis
  - Extract and identify the full set of **IP subnets** referenced in the input.
  - These subnets act as **hashing keys** in an internal map or dictionary.
  - All subnets must be **de-duplicated** so each subnet is referenced only once.

  - **Checks**
    - Each subnet must parse cleanly as either an **IPv4 or IPv6 network** using the language-specific code snippets in the `references/` folder.
    - Subnets must be normalized and displayed in **CIDR slash notation**.
      - Single-host IPv4 subnets must be represented as **`/32`**
      - Single-host IPv6 subnets must be represented as **`/128`**
      
  - **ERROR** 
    - Report the following conditions as **ERROR** and require correction before continuing:

    - **Invalid subnet syntax**
      - Message: `Invalid IP prefix: unable to parse as IPv4 or IPv6 network`

    - **Non-public address space**
      - Applies to subnets that are **private, loopback, link-local, multicast, or otherwise non-public**
        - In Python, detect non-public ranges using `is_private` and related address properties as shown in `./references`.
      - Message: `Non-public IP range is not allowed in an RFC 8805 feed`

    - **RFC 8805–incompatible subnet**
      - Any subnet failing mandatory RFC 8805 constraints
      - Message: `Subnet is not valid for publication in an RFC 8805 geofeed`



   - **WARNING**
      - Flag the following conditions for **user review**, without blocking execution:

      - **Overly large IPv6 subnets**
        - Prefixes shorter than `/64`
        - Message: `IPv6 prefix is unusually large and may indicate a typo`

      - **Overly large IPv4 subnets**
        - Prefixes shorter than `/24`
        - Message: `IPv4 prefix is unusually large and may indicate a typo`


  - **Subnet Storage**
    - Once checked, store each subnet as a **key** in a map or dictionary.
    - The corresponding value must be a **custom object** containing:
      - Geolocation attributes for the subnet
      - Any user-provided hints or preferences related to that subnet's geolocation.

### Phase 4: Geolocation Quality Check

Analyze the **accuracy and consistency** of geolocation data — country codes, region codes, city names, and deprecated fields.
This phase runs after structural checks pass.

#### Country Code Analysis
  - Use the locally available data table [`ISO3166-1`](assets/iso3166-1.json) for checking.
    - JSON array of countries and territories with ISO codes
    - Each object includes:
      - `alpha_2`: two-letter country code
      - `name`: short country name
      - `flag`: flag emoji
    - This file represents the **superset of valid `alpha2code` values** for an RFC 8805 CSV
  - Check `alpha2code` (RFC 8805 Section 2.1.1.2) against the `alpha_2` attribute.
  - Sample code is available in
    [`references`](references/snippets-*.md).

  - **ERROR** 
    - **Invalid country code**
      - Condition: `alpha2code` is present but not found in the `alpha_2` set
      - Message: `Invalid country code: not a valid ISO 3166-1 alpha-2 value`


#### Region Code Analysis
  - Use the locally available data table [`ISO3166-2`](assets/iso3166-2.json) for checking.
    - JSON array of country subdivisions with ISO-assigned codes
    - Each object includes:
      - `code`: subdivision code prefixed with country code (for example, `US-CA`)
      - `name`: short subdivision name
    - This file represents the **superset of valid `region` values** for an RFC 8805 CSV
  - If a `region` value is provided (RFC 8805 Section 2.1.1.3):
    - Check that the format matches `{COUNTRY}-{SUBDIVISION}`
      (for example, `US-CA`, `AU-NSW`).
    - Check the value against the `code` attribute (already prefixed with the country code).

  - **ERROR** 
    - **Invalid region format**
      - Condition: `region` does not match `{COUNTRY}-{SUBDIVISION}`
      - Message: `Invalid region format; expected COUNTRY-SUBDIVISION (e.g., US-CA)`
    - **Unknown region code**
      - Condition: `region` value is not found in the `code` set
      - Message: `Invalid region code: not a valid ISO 3166-2 subdivision`
    - **Country–region mismatch**
      - Condition: Country portion of `region` does not match `alpha2code`
      - Message: `Region code does not match the specified country code`
    - **Region specified for small territory**
      - Condition:
        - `alpha2code` is present in the **small territories list**, AND
        - `region` is non-empty.
      - Reference:
        - Small territories identified using
          [`assets/small-territories.json`](assets/small-territories.json).
      - Message: `Region must not be specified for small territories`


#### City Name Analysis

  City names are validated using **heuristic checks only**.  
  There is currently **no authoritative dataset** available for validating city names.

  - **ERROR**
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
    - **Inconsistent casing or formatting**
      - Condition: City names with inconsistent casing, spacing, or formatting that may reduce data quality, for example:
        - `HongKong` vs `Hong Kong`
        - Mixed casing or unexpected script usage
      - Message: `City name formatting is inconsistent; consider normalizing the value`

#### Postal Code Check
  - RFC 8805 Section 2.1.1.5 explicitly **deprecates postal or ZIP codes**.
  - Postal codes can represent very small populations and are **not considered privacy-safe**
    for mapping IP address ranges, which are statistical in nature.

  - **ERROR**
    - **Postal code present**
      - Condition: A non-empty value is present in the postal/ZIP code field.
      - Message: `Postal codes are deprecated by RFC 8805 and must be removed for privacy reasons`

### Phase 5: Region Suggestion Batch Lookup**

  - **Objective**
    - Generate region suggestions for rows where a `city` is present but `region` is empty. 

  - **Preconditions**
    - Include rows where:
      - `city` is NOT empty 
      - `region` is empty
      - `alpha2code` is NOT listed in [`assets/small-territories.json`](assets/small-territories.json)

    - Exclude rows where:
      - `city` is empty
      - `region` is already populated
      - `alpha2code` belongs to a small territory

  - **Step 1 — Build Lookup Payload**
    - Create a JSON array containing only the required lookup fields:

    ```json
    [
      {
        "city": "<city>",
        "country": "<alpha2code>"
      }
    ]
    ```

    - Do NOT include duplicate city–country pairs.


  - **Step 2 — Persist Input**
    - Store the generated JSON at:

    ```
    ./run/data/region-lookup-input.json
    ```

    - Ensure the directory exists before writing.


  - **Step 3 — Invoke Mapbox MCP Tool**
    - Tool: `reverse_geocode`  
    - Server: `https://mcp.mapbox.com/mcp`

    - Send the JSON array as the request body.

  - **Step 4 — Normalize Results**
    - For each lookup entry:

      - Deduplicate suggestions by `region_code`
      - Preserve response order (assumed relevance-ranked)
      - Keep **at least three** suggestions when available
      - If fewer than three exist, keep all returned values
      - If none exist, return an empty suggestion array (do NOT raise an error)

  - **Step 5 — Persist Output**
    - Store the response at:
      - [region-lookup-output.json](./run/data/region-lookup-output.json)
      - Example structure:

      ```json
      [
        {
          "city": "San Jose",
          "country": "US",
          "suggestions": [
            {
              "region_code": "US-CA",
              "region_name": "California",
              "relevance": 0.98
            }
          ]
        }
      ]
      ```


  - **Operational Rules**
    - Perform this lookup **once per validation run** (batch mode).
    - Do NOT automatically populate the CSV `region` field.
    - Failure to retrieve suggestions must NOT block validation.

### Phase 6: Tuning & Recommendations

This phase applies **opinionated recommendations** beyond RFC 8805 — suggestions learned from real-world geofeed deployments that improve accuracy and usability.

- **SUGGESTION**

  - **City value specified for small territories**
    - Condition: A `city` value is present and `alpha2code` belongs to a **small-sized territory**
    - Reference:
      - Small territories identified using
        [`assets/small-territories.json`](assets/small-territories.json).
    - Message: `City-level granularity is usually unnecessary for small territories; consider removing the city value`

  - **Missing region code when city is specified**
    - Condition: A `city` value is present but `region` is empty.
    - Reference:
      - [region-lookup-output.json](./run/data/region-lookup-output.json).
    - Message: `Consider selecting a region code based on city name or suggested options: {REGION_CODE} – {Region Name}`

  - **Unspecified geolocation for subnet**
    - Condition: All geographical fields (`alpha2code`, `region`, `city`) are empty for a subnet.
    - Message: `Confirm whether this subnet is intentionally marked as do-not-geolocate or missing location data`



### Phase 7: Generate Tuning Report

- Generate a **deterministic, self-contained HTML validation report** using **HTML5** and **inline CSS only** (no external assets).  
- If inline rendering is supported by the UI, render the report directly. Otherwise, write the HTML report to `./run/report/`, using the **input CSV filename** (with a `.html` extension), and open it with the system default browser.
- Prefer Bootstrap layout classes, tables, badges, alerts, and collapsible UI elements for readability and consistency.

#### Summary Section

Render a **fixed metrics panel** at the top of the report, consisting of **four separate tables stacked vertically (top-down)**.
Each table must appear **one after the other**, never side-by-side.

##### Table layout and styling requirements

- Use `./scripts/templates/report_header.html` as the **visual and structural reference** for the metrics panel.
- **Style the template and all summary tables using Bootstrap (v5.3.x)** for layout, spacing, and typography.
  - Use Bootstrap table utilities (`.table`, `.table-bordered`, `.table-sm`, etc.) where appropriate.
  - Use Bootstrap spacing and container classes to enforce margins and alignment.
- All tables must have a **consistent width** across the report.
- Table width must **fit within the page viewport** and respect horizontal margins.
- Apply equal **left and right margins** so tables are visually centered.
- Use a **clean, readable report style**:
  - Clear table borders
  - Bold header row
  - Adequate cell padding
- Do not allow tables to overflow horizontally.
- Tables must scale cleanly for typical desktop screen widths and printing.

Each table must use a **two-column key–value layout**:
- **Left column**: metric label
- **Right column**: computed value only


###### Feed Metadata

- Input file: display the source as a URL if provided; otherwise show the local file path and resolved filename.
- Timestamp must be UTC, ISO-8601.

| Metric               | Value |
|----------------------|-------|
| Input file           |       |
| Tuning timestamp     |       |


###### Entries

| Metric                     | Value |
|----------------------------|-------|
| Total entries              |       |
| IPv4 entries               |       |
| IPv6 entries               |       |


###### Analysis Summary

| Metric            | Value |
|-------------------|-------|
| **ERROR** count   |       |
| **WARNING** count |       |
| **OK** count      |       |


###### Geographical Accuracy Classification

| Metric                     | Value |
|----------------------------|-------|
| City-level accuracy        |       |
| Region-level accuracy      |       |
| Country-level accuracy     |       |
| Do-not-geolocate entries   |       |


#### Results Table

Render a **single, stable, sortable HTML table** with **one row per input CSV entry**.
- Preserve the **original CSV row order** by default.
- Use `./scripts/templates/report_table.html` as the **visual and structural reference** for the table.

Columns **must appear in this exact order**:

| Column    | Description                                               |
|-----------|-----------------------------------------------------------|
| Line      | 1-based CSV line number                                   |
| IP Prefix | Normalized CIDR notation                                  |
| Country   | `alpha2code` with the corresponding country flag emoji    |
| Region    | Region code or empty                                      |
| City      | City name or empty                                        |
| Status    | ERROR, WARNING, SUGGESTION, or OK                         |
| Messages  | Ordered list of issues and suggestions                    |

##### Large Feed Optimization

- If the input CSV contains **10,000 or more entries**, the Results Table MUST include **only rows with issues** (ERROR, WARNING, SUGGESTION status) to prevent browser performance degradation.
- OK entries are excluded from the table but **still counted** in the summary statistics.
- This threshold balances completeness with browser rendering performance — a 10K-row table renders smoothly, while 100K+ rows cause browsers to hang.

##### Column Definitions

- **Line**  
  - The **1-based line number** from the original input CSV file.  
  - This value must refer to the physical line in the source file after comment handling.

- **IP Prefix**  
  - The IP subnet expressed in **normalized CIDR notation**.  

- **Country**  
  The two-letter ISO 3166-1 `alpha2code` associated with the subnet.  
  - Always display the **country flag emoji** alongside the code in the HTML report.
  - If the country code is invalid, display the raw value with the emoji omitted or replaced according to the rules.

- **Region**  

The **ISO 3166-2 subdivision code** (for example, `US-CA`).

  - UI Behavior
    - Render the **Region** field as a **dropdown menu**.
    - The **default selected value** MUST be the value provided in the CSV.
    - If the CSV value is present and valid, **skip any lookup** and proceed to the next step.

  - Auto-suggestion (Fallback)
    - If the CSV value is **empty or missing**:
      - Invoke the [Mapbox](https://mcp.mapbox.com/mcp) MCP server **reverse-geocode** tool using the **City** field.
      - Populate the dropdown with **at least three suggested region codes**.
      - Suggestions SHOULD be ordered by **confidence or relevance**, when available.
      - Leave the field empty if no region is specified or applicable.
      - The user MAY override the suggested value by selecting a different option from the dropdown.

- **City**  
  The city name associated with the subnet.  
  - Leave empty if no city is provided.

- **Status**  
  - The **highest severity level** assigned to the row after all phases complete.  
  - Severity order: **ERROR** > **WARNING** > **SUGGESTION** > **OK**


- **Messages**  
  An **ordered list** of issues and suggestions for the row.  
  - Includes **ERROR**, **WARNING** and  **SUGGESTION**.

##### Filtering and Visual Encoding

- Apply **row-level visual styling** based on status:
  - **ERROR**: light red background
  - **WARNING**: light yellow background
  - **SUGGESTION**: light blue or neutral background
  - **OK**: light green background

- Provide a **status filter dropdown** positioned **above the table**, aligned with the table title.
  - Options:
    - **ERROR**
    - **WARNING**
    - **SUGGESTION**
    - **OK**
    - All (default)

- Filtering must:
  - Operate on the **single table**
  - Preserve original row order
  - Toggle visibility only (do not remove rows from the DOM)


#### Output Guarantees

- Report must be readable in any modern browser without external network dependencies.
- All Bootstrap CSS/JS must be referenced from local `assets/bootstrap-5.3.8-dist/` files.
- All values must be derived **only from analysis output**, not recomputed heuristically.
