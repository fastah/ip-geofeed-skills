---
name: csv-rfc8805-validation
description: Basic syntax validation of a CSV-format file with IP geofeed information.
---

# First-level syntax validation of IP Geolocation (IP geofeed) CSV-formatted files

This skills helps insure the IP geolocation CSV feed valid is (a) in fact a valid CSV file, and (b) is formatted according to the minimum requirements of the [RFC 8805 internet standard - A Format for Self-Published IP Geolocation Feeds](https://www.rfc-editor.org/rfc/rfc8805.txt)

## When to use this skill

Use this skill when you need to:
- Accept a new CSV-formatted IP geolocation aka geofeed file
- Debug problems with it
- Sanitize and validate it so that it's suitablef more advanced tests

## Creating tests

1. Review the [test template](./test-template.js) for the standard test structure
2. Identify the user flow to test
3. Create a new test file in the `tests/` directory
4. Use Playwright's locators to find elements (prefer role-based selectors)
5. Add assertions to verify expected behavior

## Running tests

To run tests locally:
```bash
npx playwright test
```

To debug tests:
```bash
npx playwright test --debug
```

## Best practices

- TBD
