---
name: validator
description: Helps author and validate a CSV-format IP-based geolocation feed file against RFC 8805 and current best practices.
license: Apache-2.0
metadata:
  author: Sid Mathur <support@getfastah.com>
  version: "0.1"
compatibility: Requires Python, csvkit CLI, and access to the internet
---

# Validator for RFC 8805 IP Geolocation CSV feeds

This skill helps ensure that an IP geolocation CSV feed is (a) a valid CSV file, (b) has valid syntax and semantics as per the [RFC 8805 - A Format for Self-Published IP Geolocation Feeds](references/rfc8805.txt), and (c) uses current best practices.

## When to use this skill

- Use this skill when a user asks for help writing, validating, or publishing an IP geolocation feed file in CSV format.
- Troubleshoot a CSV-format IP geolocation feed file in RFC 8805 - for syntax as well as semantic errors.
- Audience for this tool: Network Operators, Administrators, and Engineers who manage publicly-routable IP addresses on the internet. Organizationally - ISPs, mobile carriers, cloud companies, hosting, co-location, and Internet Exchange operators, including satellite internet providers.
- Do NOT use this skill for private-network IP address management, this is only for publicly-routable IPs.

## Prerequisite: CLI tools and/or languages

1. Ensure [`csvkit` v2](https://csvkit.readthedocs.io/en/latest/index.html), the Python-powered CLI suite for CSV manipulation is installed and ready for invocation. `csvkit` is *best installed via `pipx`; system pip installs are discouraged*. For OS-specific guidance, read [INSTALL-GUIDE-CSVKIT.md](references/INSTALL-GUIDE-CSVKIT.md).
    - Verify that the `csvkit` suite's binaries are callable from the CLI; for example `csvcut` should report version `2.x.y` to stdout when called as follows:

        ```shell
        csvcut --version
        ```

2. If unable to use `csvkit`, write `Go` programs using the guidance in [snippets-golang-go.md](references/snippets-golang-go.md), or `Python` scripts using [snippets-python3.md](references/snippets-python3.md).

## Phase 1: Deep Research

Read Section 1 ("Introduction") and Section 2 ("Self-Published IP Geolocation Feeds") of the plain text [RFC 8805 - A Format for Self-Published IP Geolocation Feeds](references/rfc8805.txt) to understand authoring requirements of an IP geolocation feed file. This covers both syntax and semantics.

## Phase 2: User input

- If the user hasn't already provided a list of IP subnets or ranges (occasionally called `inetnum`, `inet6num`), ask them for it. They may provide it via text chat, local file, or a remote URL.
- Normalize everything to UTF-8 encoding.
- In the first pass, find the set of subnets they are referring to; this is the hashing key in your logical map or dictionary, and must eventually be de-duplicated and referenced once.

- Run *validation checks* of the following types; flag errors to the user for correction:

  - Subnets or networks must parse cleanly to either IPv4 or IPv6 network type. Use the language-specific code snippets provided in the `references/` folder.
  - Subnets are pretty-printed to the user in slash notation. Remember that single-host subnets are /32 (prefix is 32 bits) in IPv4, and /128 (prefix is 128 bits) in IPv6.
  - Flag *overly large subnets* as potential errors or typos for further user review:
    - For IPv6: prefixes with fewer bits than /64 (e.g., `2001:db8::/32`) are likely typos, as this network has 2^(128-32) hosts—far too large for an IP geolocation feed.
    - For IPv4: prefixes smaller than /24 should be flagged.

- Maintain a map or dictionary. Once subnets are validated as valid IPv4 or IPv6 subnets, use them as keys in a map or dictionary. The value should be a custom type/object containing the geolocation attributes for that subnet, plus any user-specified hints or preferences for that subnet's geolocation.

## Phase 3: Syntax validation

### CSV syntax test using `csvkit` CLI tool

1. Ensure there are 4 columns in the CSV. Comment lines are OK.
    - The columns may or may not be labeled with a header row.
    - The implicit headers are `ip_prefix,alpha2code,region,city`.
    - See example user input CSV in [`example/01-user-input-rfc8805-feed.csv`](example/01-user-input-rfc8805-feed.csv).

2. Cleanse the CSV by using `csvcut` from the `csvkit` toolset as follows. Note that this single command fixes any linting issues with the CSV while also dropping any column after the fourth column:

    ```shell
    csvcut -c 1-4 --add-bom example/01-user-input-rfc8805-feed.csv
    ```

3. Optionally, remove any comment rows that use a `#` in the first column. Note that this will also remove the header row if present, but headers are optional per RFC 8805:

    ```shell
    csvgrep --invert-match -c 1 -r '#' example/01-user-input-rfc8805-feed.csv
    ```

4. Do not allow CSVs with a fifth column for `postal_code` or ZIP code to proceed past this stage. If the user asks why, explain:
    - [Section 2.1.1.5 of RFC 8805](https://www.rfc-editor.org/rfc/rfc8805.txt) explicitly deprecates postal/ZIP codes.
    - Postal codes can represent very small populations, so they are not considered privacy-safe when mapping IP address ranges (which are statistical in nature) to low-population-density geographical regions.

## Phase 4: Semantic validation

Validate geolocation information, accuracy, place names, and ISO codes.

### Locally-available data tables

- [`assets/iso3166-1.json`](assets/iso3166-1.json): JSON array of countries/territories with ISO codes. Each object has a 2-letter country code in `alpha_2`. This is the superset of valid `alpha2code` values in an RFC 8805 CSV. Other attributes include `flag` (flag emoji) and `name` (short name).

- [`assets/iso3166-2.json`](assets/iso3166-2.json): JSON array of subdivisions with ISO-assigned 2- or 3-letter codes. Each object has `code` (e.g., `US-CA`), which is the superset of valid `region` values in an RFC 8805 CSV. `name` is the short name.

### Country code validation

- Validate `alpha2code` (RFC 8805 Section 2.1.1.2) against [`assets/iso3166-1.json`](assets/iso3166-1.json), specifically the `alpha_2` JSON attribute. Sample code snippets are available in [references/snippets-*.md](references).
- Flag an `alpha2code` not in the data file's `alpha_2` set as ERROR. Flag an empty `alpha2code` as WARNING (the RFC allows empty values when geolocation should not be attempted, e.g., for routers).

### Region code validation

- If a `region` is provided (RFC 8805 Section 2.1.1.3), validate that the format matches `{COUNTRY}-{SUBDIVISION}` (e.g., `US-CA`, `AU-NSW`).
- Validate against [`assets/iso3166-2.json`](assets/iso3166-2.json), matching the `code` JSON attribute (already prefixed with the country code).

### City name validation

- Flag placeholder values as ERROR: `undefined`, `Please select`, `null`, `N/A`, `TBD`, `unknown`.
- Flag truncated/abbreviated names or airport codes as ERROR: `LA`, `Frft`, `sin01`, `LHR`, `SIN`, `MAA`.
- Flag inconsistent casing as WARNING: `HongKong` vs `Hong Kong` vs `香港`.
- There is no built-in dataset for validating city names, but an MCP server is planned.

## Phase 5: Best practices scan

- Flag overlapping subnets (e.g., /27 and /26 for the same base IP).
- Suggest aggregation for consecutive single-host entries (/32, /31).
- Recommend adding region codes when a city is specified.

## Phase 6: Output format

Generate a validation report containing:

- Summary statistics (error/warning/info counts).
- Per-entry validation table (HTML or Markdown).
- Actionable recommendations list.
