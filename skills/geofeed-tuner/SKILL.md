---
name: geofeed-tuner
description: Helps author and validate a CSV-format IP-based geolocation feed file against RFC 8805 and current best practices.
license: Apache-2.0
metadata:
  author: Sid Mathur <support@getfastah.com>
  version: "0.1"
compatibility: Requires Python, csvkit CLI, and access to the internet
---

# Validator for RFC 8805 IP Geolocation CSV Feeds

This skill validates an IP geolocation feed provided in CSV format by ensuring that it:
- Is a valid CSV file
- Conforms to the syntax and semantics defined in  
  [RFC 8805 – A Format for Self-Published IP Geolocation Feeds](references/rfc8805.txt)
- Follows current best practices for publishing self-managed IP geolocation data

## When to Use This Skill

- Use this skill when a user asks for help **authoring, validating, or publishing** an IP geolocation feed file in CSV format.
- Use it to **troubleshoot RFC 8805–compliant CSV geolocation feeds**, including both syntax and semantic validation errors.
- **Intended audience**:
  - Network operators, administrators, and engineers responsible for publicly routable IP address space
  - Organizations such as ISPs, mobile carriers, cloud providers, hosting and colocation companies, Internet Exchange operators, and satellite internet providers
- **Do not use** this skill for private or internal IP address management; it applies **only to publicly routable IP addresses**.


## Prerequisite: CLI Tools and/or Languages

- **Python 3** is required.

## Processing Pipeline: Sequential Phase Execution

- All phases of the skill must be executed **in order**, from Phase 1 through Phase 6.
- Each phase depends on the successful completion of the previous phase.  
  - For example, **syntax and input validation** must complete before **semantic validation** can run.

- The phases are:

  - **Phase 1: Deep Research**  
    Understand RFC 8805 requirements for self-published IP geolocation feeds.

  - **Phase 2: User Input**  
    Collect IP subnet data from local files or remote URLs.

  - **Phase 3: Syntax Validation**  
    Validate CSV format, structure, and IP subnet correctness.

  - **Phase 4: Semantic Validation**  
    Validate country codes, region codes, city names, and postal code rules.

  - **Phase 5: Best Practices Scan**  
    Recommend missing region codes, confirm user intent for unspecified subnets, and enforce best practices.

  - **Phase 6: HTML Report Generation**  
    Generate a **HTML report** summarizing validation results, errors, and warnings.

- **Validation Script Generation**
  - Generate a **single validation script** that incorporates **all steps from Phases 2–6**.
  - Store the generated script in the `./run/scripts` directory.
  - The script must include:
    - Load CSV input — download if a URL is provided, otherwise use local (**Phase 2**).
    - CSV and IP syntax checks (**Phase 3**).
    - Semantic validations including country, region, city, and postal code checks (**Phase 4**).
    - Best practices warnings and recommendations (**Phase 5**).
    - HTML report generation summarizing validation results (**Phase 6**).

- Users or automation agents should **not skip phases**, as each phase provides critical checks or data transformations required for the next stage.



### Phase 1: Deep Research

Read Section 1 (**Introduction**) and Section 2 (**Self-Published IP Geolocation Feeds**) of the plain-text  
[RFC 8805 – A Format for Self-Published IP Geolocation Feeds](references/rfc8805.txt).

The goal of this phase is to understand the **authoring requirements** for an IP geolocation feed file, including:
- The overall purpose and scope of RFC 8805
- The required and optional data elements
- The expected syntax and semantics of a compliant feed

This research phase establishes the conceptual foundation needed before performing any input handling, validation, or processing in later phases.


### Phase 2: User Input

- If the user has not already provided a list of IP subnets or ranges (sometimes referred to as `inetnum` or `inet6num`), prompt them to supply it. The input may be provided via:
  - Text pasted into the chat
  - A local CSV file
  - A remote URL pointing to a CSV file

- If the input is a **remote URL**, download the CSV file into the `./run/data` directory before processing.
- If the input is a **local file**, continue processing it directly without downloading.
- Normalize all input data to **UTF-8** encoding.



### Phase 3: Syntax Validation

Syntax validation verifies the **input format and structure** before any geolocation-specific checks. **Critical syntax errors** must halt further processing.

#### CSV Validation

This subsection defines validation rules specific to **CSV-formatted input files** used for RFC 8805 IP geolocation feeds.
The goal is to ensure the file can be parsed reliably and normalized into a **consistent internal representation**.

- **CSV Structure Validation**
  - If `pandas` is available, use it for CSV parsing.
  - Otherwise, fall back to Python’s built-in `csv` module.

  - Ensure the CSV contains **exactly 4 or 5 logical columns**.
    - Comment lines are allowed.
    - A header row **may or may not** be present.
    - If no header row exists, assume the implicit column order:
      ```
      ip_prefix, alpha2code, region, city, postal code (deprecated)
      ```
    - Refer to the example input file:
      [`example/01-user-input-rfc8805-feed.csv`](example/01-user-input-rfc8805-feed.csv)

- **CSV Cleansing and Normalization**
  - Clean and normalize the CSV using Python logic equivalent to the following operations:
    - Select only the **first five columns**, dropping any columns beyond the fifth.
    - Write the output file with a **UTF-8 BOM**.
    - Optionally remove comment rows where the **first column begins with `#`**.
    - This will also remove a header row if it begins with `#`.

- **Notes**
  - Both implementation paths (`pandas` and built-in `csv`) must write output using
    the `utf-8-sig` encoding to ensure a **UTF-8 BOM** is present.

#### IP Validation
  - Extract and identify the full set of **IP subnets** referenced in the input.
  - These subnets act as **hashing keys** in an internal map or dictionary.
  - All subnets must be **de-duplicated** so each subnet is referenced only once.

  - **Validation Checks**
    - Each subnet must parse cleanly as either an **IPv4 or IPv6 network** using the language-specific code snippets in the `references/` folder.
    - Subnets must be normalized and displayed in **CIDR slash notation**.
      - Single-host IPv4 subnets must be represented as **`/32`**
      - Single-host IPv6 subnets must be represented as **`/128`**
    - Flag **overly large subnets** as potential errors or typos for user review:
      - **IPv6**: Prefixes shorter than `/64` (for example, `2001:db8::/32`) should be flagged, as they represent an unrealistically large address space for an IP geolocation feed.
      - **IPv4**: Prefixes shorter than `/24` should be flagged.
    - Flag **non-public IP address ranges** that are accidentally or intentionally included in the subnet list.
    - Treat any subnet identified as **private, loopback, link-local, multicast, or otherwise non-public** as invalid for an RFC 8805 feed.
    - In Python, use the built-in `is_private` (and related address properties) as shown in the code snippets provided in the `references/` folder.
    - Report detected non-public subnets to the user as **ERRORS** and require correction before continuing.


  - **Subnet Storage**
    - Once validated, store each subnet as a **key** in a map or dictionary.
    - The corresponding value must be a **custom object** containing:
      - Geolocation attributes for the subnet
      - Any user-provided hints or preferences related to that subnet’s geolocation.

### Phase 4: Semantic Validation

Validate **geolocation information**, **accuracy**, **place names**, and **ISO codes**.
Semantic validation must run only after **syntax validation** completes successfully.

#### Country Code Validation
  - Use the locally available data table [`assets/iso3166-1.json`](assets/iso3166-1.json) for validation.
    - JSON array of countries and territories with ISO codes
    - Each object includes:
      - `alpha_2`: two-letter country code
      - `name`: short country name
      - `flag`: flag emoji
    - This file represents the **superset of valid `alpha2code` values** for an RFC 8805 CSV
  - Validate `alpha2code` (RFC 8805 Section 2.1.1.2) against the `alpha_2` attribute.
  - Sample validation code is available in
    [`references/snippets-*.md`](references).
  - Flag an `alpha2code` not present in the `alpha_2` set as **ERROR**.
  - Flag an empty `alpha2code` as **WARNING**.
    - RFC 8805 allows empty values when geolocation should not be attempted
      (for example, infrastructure devices such as routers).

#### Region Code Validation
  - Use the locally available data table [`assets/iso3166-2.json`](assets/iso3166-2.json) for validation.
    - JSON array of country subdivisions with ISO-assigned codes
    - Each object includes:
      - `code`: subdivision code prefixed with country code (for example, `US-CA`)
      - `name`: short subdivision name
    - This file represents the **superset of valid `region` values** for an RFC 8805 CSV
  - If a `region` value is provided (RFC 8805 Section 2.1.1.3):
    - Validate that the format matches `{COUNTRY}-{SUBDIVISION}`
      (for example, `US-CA`, `AU-NSW`).
    - Validate the value against the `code` attribute(already prefixed with the country code).

#### City Name Validation
  - Flag placeholder values as **ERROR**:
    - `undefined`, `Please select`, `null`, `N/A`, `TBD`, `unknown`
  - Flag truncated names, abbreviations, or airport codes as **ERROR**:
    - `LA`, `Frft`, `sin01`, `LHR`, `SIN`, `MAA`
  - Flag inconsistent casing or formatting as **WARNING**:
    - `HongKong` vs `Hong Kong` vs `香港`
  - There is currently **no authoritative dataset** available for validating city names.

#### Postal Code Validation
  - RFC 8805 Section 2.1.1.5 explicitly **deprecates postal or ZIP codes**.
  - Postal codes can represent very small populations and are **not considered privacy-safe**
    for mapping IP address ranges, which are statistical in nature.
  - If a postal code is present:
    - Produce an **ERROR** indicating that postal codes are deprecated.
    - Indicate that the field should be **removed for privacy reasons**.

### Phase 5: Best Practices Scan

- **Region Code Recommendations**
  - Recommend **adding region codes** whenever a city is specified.
  - Ignore the absence of region code when country code matches a **small-sized territory** (by area or population) where state/province usage is uncommon. Load and use the JSON array of 2-letter country codes in [assets/small-territories.json](assets/small-territories.json) for this check.

- **Subnet Confirmation**
  - Recommend confirming with the user when a subnet is left **unspecified for all geographical columns**.
    - Warn the user whether they **intend for the subnet to remain un-geolocated** (literal interpretation of RFC 8805),  
      or whether they **forgot to specify** the country, state, or city for it.


### Phase 6: HTML Report Generation

- Generate a **deterministic, self-contained HTML validation report** using **HTML5** and **inline CSS only** (no external assets).  
- If inline rendering is supported by the UI, render the report directly. Otherwise, write the HTML report to `./run/report/`, using the **input CSV filename** (with a `.html` extension), and open it with the system default browser.
- Where applicable, use **Bootstrap (v5.3.x)** classes and components to style the report for readability and consistency.
  - Prefer layout, tables, badges, alerts, and collapsible UI elements from Bootstrap.
  - Do not require a build step; use CDN-compatible Bootstrap assets only.
  - Reference: [Bootstrap documentation](https://raw.githubusercontent.com/twbs/bootstrap/refs/tags/v5.3.8/site/src/content/docs/getting-started/introduction.mdx)



#### Summary Section

Render a **fixed metrics panel** at the top of the report, consisting of **four separate tables stacked vertically (top-down)**.
Each table must appear **one after the other**, never side-by-side.

##### Table layout and styling requirements

- Use `./templates/report_header.html` as the **visual and structural reference** for the metrics panel.
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
| Validation timestamp |       |


###### Entries

| Metric                     | Value |
|----------------------------|-------|
| Total entries              |       |
| IPv4 entries               |       |
| IPv6 entries               |       |


###### Validation Results

| Metric        | Value |
|---------------|-------|
| ERROR count   |       |
| WARNING count |       |
| INFO count    |       |


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
- Use `./templates/report_table.html` as the **visual and structural reference** for table.

Columns **must appear in this exact order**:

| Column    | Description                                               |
|-----------|-----------------------------------------------------------|
| Line      | 1-based CSV line number                                   |
| IP Prefix | Normalized CIDR notation                                  |
| Country   | `alpha2code` with the corresponding country flag emoji    |
| Region    | Region code or empty                                      |
| City      | City name or empty                                        |
| Severity  | ERROR, WARNING, BEST_PRACTICE, or INFO                    |
| Messages  | Ordered list of validation messages and inferred accuracy |

##### Column Definitions

- **Line**  
  - The **1-based line number** from the original input CSV file.  
  - This value must refer to the physical line in the source file after comment handling.

- **IP Prefix**  
  - The IP subnet expressed in **normalized CIDR notation**.  

- **Country**  
  The two-letter ISO 3166-1 `alpha2code` associated with the subnet.  
  - Always display the **country flag emoji** alongside the code in the HTML report.
  - If the country code is invalid, display the raw value with the emoji omitted or replaced according to validation rules.

- **Region**  

The **ISO 3166-2 subdivision code** (for example, `US-CA`).

  - UI Behavior
    - Render the **Region** field as a **dropdown menu**.
    - The **default selected value** MUST be the value provided in the CSV.
    - If the CSV value is present and valid, **skip any lookup** and proceed to the next step.

  - Auto-suggestion (Fallback)
    - If the CSV value is **empty or missing**:
      - Invoke the [Blackbox](https://mcp.mapbox.com/mcp) MCP server **reverse-geocode** tool using the **City** field.
      - Populate the dropdown with **at least three suggested region codes**.
      - Suggestions SHOULD be ordered by **confidence or relevance**, when available.
      - Leave the field empty if no region is specified or applicable.
      - The user MAY override the suggested value by selecting a different option from the dropdown.

- **City**  
  The city name associated with the subnet.  
  - Leave empty if no city is provided.

- **Severity**  
  - The **highest severity level** assigned to the row after all validation phases complete.  
  - Severity order: `ERROR` > `WARNING` > `BEST_PRACTICE` > `INFO`


- **Messages**  
  An **ordered list** of validation messages for the row.  
  - Includes  **ERROR**, **WARNING** and  **OBSERVATION**.

##### Filtering and Visual Encoding

- Apply **row-level visual styling** based on severity:
  - **ERROR**: light red background
  - **WARNING**: light yellow background
  - **BEST_PRACTICE**: light blue or neutral background
  - **INFO**: light green background

- Provide a **severity filter dropdown** positioned **above the table**, aligned with the table title.
  - Options:
    - ERROR
    - WARNING
    - BEST_PRACTICE
    - INFO
    - All (default)

- Filtering must:
  - Operate on the **single table**
  - Preserve original row order
  - Toggle visibility only (do not remove rows from the DOM)


#### Output Guarantees

- Report must be readable in any modern browser without JavaScript dependencies.
- No network access is permitted during report generation.
- All values must be derived **only from validation output**, not recomputed heuristically.

### Phase 7: Final Consistency and Completeness Check

Perform a final pass over the validated data and generated outputs to ensure nothing was missed or left inconsistent.