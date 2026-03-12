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
		sourceTableData := []geofeed_validation.Netname{}
		rirPathPrefix := geofeed_validation.GetSourceTablePath(rir.Name)

		for _, netname := range rir.Netnames {
			fmt.Println("Processing Netname:", netname.Name)
			netnameTableData := []geofeed_validation.Record{}
			sanitizedNetname := geofeed_validation.GetNetnameTablePath(netname.Name)
			netnamePathPrefix := filepath.Join(rirPathPrefix, sanitizedNetname)

			for index, record := range netname.Records {
				reportRelativePath := fmt.Sprintf("%d.html", index+1)
				reportPath := filepath.Join(netnamePathPrefix, reportRelativePath)

				err := GeofeedValidation(record.Geofeed, reportPath, limitEntries)
				if err != nil {
					fmt.Printf("Error processing Geofeed: %v\n", err)
					continue
				} else {
					fmt.Printf("Successfully processed Geofeed: %s\n", record.Geofeed)
				}

				record.ReportURL = reportRelativePath
				netnameTableData = append(netnameTableData, record)
			}

			if len(netnameTableData) == 0 {
				fmt.Printf("No valid records found for Netname: %s\n", netname.Name)
				continue
			}

			netnameTableRelativePath := filepath.Join(sanitizedNetname, "index.html")
			err := html_template.GenerateNetnameHTMLTable(netnameTableData, filepath.Join(rirPathPrefix, netnameTableRelativePath))
			if err != nil {
				fmt.Printf("Error generating Netname HTML table: %v\n", err)
				continue
			} else {
				fmt.Printf("Successfully generated Netname HTML table for: %s\n", netname.Name)
			}
			sourceTableData = append(sourceTableData, geofeed_validation.Netname{
				Name:     netname.Name,
				TableURL: netnameTableRelativePath,
			})
		}

		if len(sourceTableData) == 0 {
			fmt.Printf("No valid records found for RIR: %s\n", rir.Name)
			continue
		}

		sourceTableURL := filepath.Join(rirPathPrefix, "index.html")
		err := html_template.GenerateSourceHTMLTable(sourceTableData, rir.Name, sourceTableURL)
		if err != nil {
			fmt.Printf("Error generating Source HTML table: %v\n", err)
			continue
		} else {
			fmt.Printf("Successfully generated Source HTML table for: %s\n", rir.Name)
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
	entries := geofeed_validation.GetEntriesFromServer(rows)
	err = geofeed_validation.ValidateEntries(entries)
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
