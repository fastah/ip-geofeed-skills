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

- All phases of the skill must be executed **in order**, from Phase 1 through Phase 7.
- Each phase depends on the successful completion of the previous phase.  
  - For example, **structure checks** must complete before **quality analysis** can run.

- The phases are:

  - **Phase 1: Understand the Standard**  
    Learn RFC 8805 requirements for self-published IP geolocation feeds.

  - **Phase 2: Gather Input**  
    Collect IP subnet data from local files or remote URLs.

  - **Phase 3: Structure & Format Check**  
    Verify CSV format, structure, and IP subnet correctness.

  - **Phase 4: Geolocation Quality Check**  
    Analyze country codes, region codes, city names, and deprecated fields.

  - **Phase 5: Tuning & Recommendations**  
    Apply opinionated best practices and suggest improvements.

  - **Phase 6: Generate Tuning Report**  
    Create an HTML report summarizing the analysis, issues, and suggestions.

  - **Phase 7: Final Review**  
    Perform a final pass to ensure consistency and completeness.

- **Tuning Script Generation**
  - Generate a **single Python script** that incorporates **all steps from Phases 2–6**.
  - Store the generated script in the `./run/` directory.
  - The script must include:
    - Load CSV input — download if a URL is provided, otherwise use local (**Phase 2**).
    - CSV and IP structure checks (**Phase 3**).
    - Geolocation quality analysis including country, region, city, and postal code checks (**Phase 4**).
    - Best practices and improvement suggestions (**Phase 5**).
    - HTML report generation summarizing results (**Phase 6**).

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
    - Flag **overly large subnets** as potential errors or typos for user review:
      - **IPv6**: Prefixes shorter than `/64` (for example, `2001:db8::/32`) should be flagged, as they represent an unrealistically large address space for a geolocation feed.
      - **IPv4**: Prefixes shorter than `/24` should be flagged.
    - Flag **non-public IP address ranges** that are accidentally or intentionally included in the subnet list.
    - Treat any subnet identified as **private, loopback, link-local, multicast, or otherwise non-public** as invalid for a geofeed.
    - In Python, use the built-in `is_private` (and related address properties) as shown in the code snippets provided in the `references/` folder.
    - Report detected non-public subnets to the user as **ERRORS** and require correction before continuing.


  - **Subnet Storage**
    - Once checked, store each subnet as a **key** in a map or dictionary.
    - The corresponding value must be a **custom object** containing:
      - Geolocation attributes for the subnet
      - Any user-provided hints or preferences related to that subnet's geolocation.

### Phase 4: Geolocation Quality Check

Analyze the **accuracy and consistency** of geolocation data — country codes, region codes, city names, and deprecated fields.
This phase runs after structural checks pass.

#### Country Code Analysis
  - Use the locally available data table [`assets/iso3166-1.json`](assets/iso3166-1.json) for checking.
    - JSON array of countries and territories with ISO codes
    - Each object includes:
      - `alpha_2`: two-letter country code
      - `name`: short country name
      - `flag`: flag emoji
    - This file represents the **superset of valid `alpha2code` values** for an RFC 8805 CSV
  - Check `alpha2code` (RFC 8805 Section 2.1.1.2) against the `alpha_2` attribute.
  - Sample code is available in
    [`references/snippets-python3.md`](references/snippets-python3.md).
  - Flag an `alpha2code` not present in the `alpha_2` set as **ERROR**.
  - Flag an empty `alpha2code` as **WARNING**.
    - RFC 8805 allows empty values when geolocation should not be attempted
      (for example, infrastructure devices such as routers).

#### Region Code Analysis
  - Use the locally available data table [`assets/iso3166-2.json`](assets/iso3166-2.json) for checking.
    - JSON array of country subdivisions with ISO-assigned codes
    - Each object includes:
      - `code`: subdivision code prefixed with country code (for example, `US-CA`)
      - `name`: short subdivision name
    - This file represents the **superset of valid `region` values** for an RFC 8805 CSV
  - If a `region` value is provided (RFC 8805 Section 2.1.1.3):
    - Check that the format matches `{COUNTRY}-{SUBDIVISION}`
      (for example, `US-CA`, `AU-NSW`).
    - Check the value against the `code` attribute (already prefixed with the country code).

#### City Name Analysis
  - Flag placeholder values as **ERROR**:
    - `undefined`, `Please select`, `null`, `N/A`, `TBD`, `unknown`
  - Flag truncated names, abbreviations, or airport codes as **ERROR**:
    - `LA`, `Frft`, `sin01`, `LHR`, `SIN`, `MAA`
  - Flag inconsistent casing or formatting as **WARNING**:
    - `HongKong` vs `Hong Kong` vs `香港`
  - There is currently **no authoritative dataset** available for city name verification.

#### Postal Code Check
  - RFC 8805 Section 2.1.1.5 explicitly **deprecates postal or ZIP codes**.
  - Postal codes can represent very small populations and are **not considered privacy-safe**
    for mapping IP address ranges, which are statistical in nature.
  - If a postal code is present:
    - Produce an **ERROR** indicating that postal codes are deprecated.
    - Indicate that the field should be **removed for privacy reasons**.

### Phase 5: Tuning & Recommendations

This phase applies **opinionated recommendations** beyond RFC 8805 — suggestions learned from real-world geofeed deployments that improve accuracy and usability.

- **Region Code Recommendations**
  - Recommend **adding region codes** whenever a city is specified.
  - Ignore the absence of region code when country code matches a **small-sized territory** (by area or population) where state/province usage is uncommon. Load and use the JSON array of 2-letter country codes in [assets/small-territories.json](assets/small-territories.json) for this check.

- **Subnet Confirmation**
  - Recommend confirming with the user when a subnet is left **unspecified for all geographical columns**.
    - Warn the user whether they **intend for the subnet to remain un-geolocated** (literal interpretation of RFC 8805),  
      or whether they **forgot to specify** the country, state, or city for it.


### Phase 6: Generate Tuning Report

- Generate a **self-contained HTML report** summarizing the analysis, issues, and improvement suggestions.
- The report must use **local Bootstrap 5.3.8 assets** bundled in [`assets/bootstrap-5.3.8-dist/`](assets/bootstrap-5.3.8-dist/) for styling.
  - Reference the local CSS file: `assets/bootstrap-5.3.8-dist/css/bootstrap.min.css`
  - Reference the local JS file (if needed): `assets/bootstrap-5.3.8-dist/js/bootstrap.bundle.min.js`
  - **Do not use CDN links** — the report must work offline without network access.
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

| Metric        | Value |
|---------------|-------|
| ERROR count   |       |
| WARNING count |       |
| OK count      |       |


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
  - Severity order: `ERROR` > `WARNING` > `SUGGESTION` > `OK`


- **Messages**  
  An **ordered list** of issues and suggestions for the row.  
  - Includes **ERROR**, **WARNING**, **SUGGESTION**, and **OBSERVATION** messages.

##### Filtering and Visual Encoding

- Apply **row-level visual styling** based on status:
  - **ERROR**: light red background
  - **WARNING**: light yellow background
  - **SUGGESTION**: light blue or neutral background
  - **OK**: light green background

- Provide a **status filter dropdown** positioned **above the table**, aligned with the table title.
  - Options:
    - ERROR
    - WARNING
    - SUGGESTION
    - OK
    - All (default)

- Filtering must:
  - Operate on the **single table**
  - Preserve original row order
  - Toggle visibility only (do not remove rows from the DOM)


#### Output Guarantees

- Report must be readable in any modern browser without external network dependencies.
- All Bootstrap CSS/JS must be referenced from local `assets/bootstrap-5.3.8-dist/` files.
- All values must be derived **only from analysis output**, not recomputed heuristically.

### Phase 7: Final Review

Perform a final pass over the analyzed data and generated outputs to ensure nothing was missed or left inconsistent.

- Verify that all CSV rows have been processed and appear in the report.
- Confirm that error/warning/ok counts in the summary match the actual row statuses.
- Ensure no duplicate entries exist in the results table.
- Validate that all file paths and references in the report are correct.
