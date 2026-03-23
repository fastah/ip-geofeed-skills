#!/usr/bin/env python3
import argparse
import sys

from internal.geofeed import geofeeds_validation, geofeed_validation

def main():
    parser = argparse.ArgumentParser(description="IP Geofeed Validator & Tuner")
    parser.add_argument("input", help="CSV file, URL, or JSON manifest (with --bulk)")
    parser.add_argument("--bulk", action="store_true", help="Enable bulk validation mode")
    parser.add_argument(
        "--limit-entries", type=int, default=0,
        help="Limit the number of entries to validate (0 = no limit)",
    )

    args = parser.parse_args()

    try:
        if args.bulk:
            geofeeds_validation(args.input, args.limit_entries)
        else:
            geofeed_validation(args.input, "index.html", args.limit_entries)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Validation complete!")


if __name__ == "__main__":
    main()
