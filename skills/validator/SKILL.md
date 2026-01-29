---
name: validator
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

- **Python** is required.

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
  - Generate a **single validation script** that incorporates **all steps from Phases 3–6**.
  - Store the generated script in the `./scripts` directory.
  - The script must include:
    - CSV and IP syntax checks (Phase 3).
    - Semantic validations including country, region, city, and postal code checks (Phase 4).
    - Best practices warnings and recommendations (Phase 5).
    - HTML report generation summarizing validation results (Phase 6).

- Users or automation agents should **not skip phases**, as each phase provides critical checks or data transformations required for the next stage.
- Logging or reporting at each phase is recommended to **track progress and flag any corrections needed** before continuing.


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

- If the input is a **remote URL**, download the CSV file into the `./input` directory before processing.
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
  - Exclude **small-sized territories** (by area or population) where state/province usage is uncommon, e.g., `SG`, `AQ`, `CK`.

- **Subnet Confirmation**
  - Recommend confirming with the user when a subnet is left **unspecified for all geographical columns**.
    - Warn the user whether they **intend for the subnet to remain un-geolocated** (literal interpretation of RFC 8805),  
      or whether they **forgot to specify** the country, state, or city for it.


### Phase 6: HTML Report Generation

Generate an HTML validation report with the following structure. Use modern web standards (HTML5, and W3C Web APIs) with inline CSS to create minimal file clutter. OK to generate inline HTML report if the UI supports it; otherwise write out the .html to the working directory or open it for the user using the default open-with-browser system action.

#### 1. Summary header

Display rolled-up statistics at the top:

- Total entries processed
- Counts by severity: ERROR, WARNING, INFO (valid entries)
- Feed metadata: filename, timestamp, IPv4/IPv6 entry counts
- Geographical accuracy stats - subnets with city-level accuracy, with state-only accuracy, with country-level accurarcy, and "do not geolocate" signalling.

#### 2. Results table

Render a table with one row per CSV entry. Columns:

| Column | Description |
|--------|-------------|
| Line | Original CSV line number |
| IP Prefix | The subnet in CIDR notation |
| Country | `alpha2code` with flag emoji if valid |
| Region | `region` code |
| City | City name |
| Status | ERROR / WARNING / INFO |
| Messages | Validation messages for this entry. Inferred geographical accuracy. |

#### 3. Row grouping and styling

Group rows by severity for user triage:

- **ERROR** (red): Invalid entries requiring fixes before publication
- **WARNING** (yellow): Entries that may need review
- **INFO** (green): Valid entries with optional suggestions

Use collapsible sections so users can hide INFO rows and focus on problems.

#### 4. Actionable recommendations

End with a numbered list of specific fixes, e.g.:

1. "Line 42: Replace country code `UK` with `GB`"
2. Any other observations and comments.

---

**TODO: Clarify the following before implementation:**

- TODO: Add "Copy to clipboard" button for exporting valid 4-column CSV data
