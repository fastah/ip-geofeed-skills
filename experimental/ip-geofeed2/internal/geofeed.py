import os

from internal.geofeed_validation.validator import (
    validate_entries, get_metadata_from_entries, load_rir_data,
    get_source_table_path, get_netname_table_path, Netname, ValidatorRecord,
)
from internal.html_template.html import (
    generate_html_report, generate_netname_html_table, generate_source_html_table,
)
from internal.parser.parser import parse_csv, load_publishers


def geofeeds_validation(path: str, limit_entries: int = 0) -> None:
    """Bulk validation mode: processes multiple geofeeds from a JSON manifest."""
    publishers = load_publishers(path)
    rir_collection = load_rir_data(publishers)

    for rir_name, rir in rir_collection.rirs.items():
        print(f"Processing RIR: {rir_name}")
        source_table_data: list[Netname] = []
        rir_path_prefix = get_source_table_path(rir_name)

        for _, netname in rir.netnames.items():
            print(f"Processing Netname: {netname.name}")
            netname_table_data: list[ValidatorRecord] = []
            sanitized_netname = get_netname_table_path(netname.name)
            netname_path_prefix = os.path.join(rir_path_prefix, sanitized_netname)

            for index, record in enumerate(netname.records):
                report_relative_path = f"{index + 1}.html"
                report_path = os.path.join(netname_path_prefix, report_relative_path)

                try:
                    geofeed_validation(record.record.geofeed, report_path, limit_entries)
                    print(f"Successfully processed Geofeed: {record.record.geofeed}")
                except Exception as e:
                    print(f"Error processing Geofeed: {e}")
                    continue

                record.report_url = report_relative_path
                netname_table_data.append(record)

            if not netname_table_data:
                print(f"No valid records found for Netname: {netname.name}")
                continue

            netname_table_relative_path = os.path.join(sanitized_netname, "index.html")
            try:
                generate_netname_html_table(
                    netname_table_data,
                    os.path.join(rir_path_prefix, netname_table_relative_path),
                )
                print(f"Successfully generated Netname HTML table for: {netname.name}")
            except Exception as e:
                print(f"Error generating Netname HTML table: {e}")
                continue

            source_table_data.append(Netname(
                name=netname.name,
                table_url=netname_table_relative_path,
            ))

        if not source_table_data:
            print(f"No valid records found for RIR: {rir_name}")
            continue

        source_table_url = os.path.join(rir_path_prefix, "index.html")
        try:
            generate_source_html_table(source_table_data, rir_name, source_table_url)
            print(f"Successfully generated Source HTML table for: {rir_name}")
        except Exception as e:
            print(f"Error generating Source HTML table: {e}")
            continue


def geofeed_validation(path: str, output_path: str, limit_entries: int = 0) -> None:
    """Single file validation mode."""
    print(f"Processing Geofeed: {path}")

    # Parse CSV
    rows, comments, invalid_entries = parse_csv(path, limit_entries)

    # Validate entries
    entries, err_entries = validate_entries(rows)
    for err_entry in err_entries:
        print(
            f"Error validating entry: {err_entry.line}, {err_entry.ip_prefix}, "
            f"{err_entry.country_code}, {err_entry.region_code}, {err_entry.city}"
        )

    # Metadata summary
    metadata = get_metadata_from_entries(entries, path, invalid_entries)

    # Generate HTML report
    generate_html_report(entries, comments, metadata, output_path)
