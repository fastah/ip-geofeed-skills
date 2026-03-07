package geofeed

import (
	"fmt"
	"ip-geofeed/internal/geofeed_validation"
	"ip-geofeed/internal/html_template"
	"ip-geofeed/internal/parser"
	"path/filepath"
)

func GeofeedsValidation(path string, limitEntries int) error {
	publishers, err := parser.LoadPublishers(path)
	if err != nil {
		return fmt.Errorf("error loading publishers: %w", err)
	}

	RIRCollection := geofeed_validation.LoadRIRData(publishers)

	for _, rir := range RIRCollection.RIRs {
		fmt.Println("Processing RIR:", rir.Name)

		for _, netname := range rir.Netnames {
			fmt.Println("Processing Netname:", netname.Name)
			outPath := geofeed_validation.OutputPath(rir.Name, netname.Name)
			netname_table_data := []geofeed_validation.Record{}

			for index, record := range netname.Records {
				filename := fmt.Sprintf("%d.html", index+1)

				err := GeofeedValidation(record.Geofeed, filepath.Join(outPath, filename), limitEntries)
				if err != nil {
					fmt.Printf("Error processing Geofeed: %v\n", err)
					continue
				} else {
					fmt.Printf("Successfully processed Geofeed: %s\n", record.Geofeed)
				}

				record.ReportURL = filename
				netname_table_data = append(netname_table_data, record)
			}

			if len(netname_table_data) == 0 {
				fmt.Printf("No valid records found for Netname: %s\n", netname.Name)
				continue
			}
			err := html_template.GenerateNetnameHTMLTable(netname_table_data, filepath.Join(outPath, "index.html"))
			if err != nil {
				fmt.Printf("Error generating Netname HTML table: %v\n", err)
				continue
			} else {
				fmt.Printf("Successfully generated Netname HTML table for: %s\n", netname.Name)
			}
		}
	}
	return nil
}

func GeofeedValidation(path, outputPath string, limitEntries int) error {
	fmt.Println("Processing Geofeed:", path)

	// Parse CSV
	rows, comments, invalidEntries, err := parser.ParseCSV(path, limitEntries)
	if err != nil {
		return fmt.Errorf("error parsing CSV: %w", err)
	}

	// Validate entries
	entries, err := geofeed_validation.ValidateAndTuneEntries(rows)
	if err != nil {
		return fmt.Errorf("error validating entries: %w", err)
	}

	// Metadata summary
	metadata := geofeed_validation.GetMetadataFromEntries(entries, path, invalidEntries)

	// Generate HTML report
	err = html_template.GenerateHTMLReport(entries, comments, metadata, outputPath)
	if err != nil {
		return fmt.Errorf("error generating HTML report: %w", err)
	}

	return nil
}
