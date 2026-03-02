package geofeed

import (
	"fmt"
	"ip-geofeed/internal/geofeed_validation"
	"ip-geofeed/internal/html_template"
	"ip-geofeed/internal/parser"
)

func GeofeedsValidation(path string) error {
	publishers, err := parser.LoadPublishers(path)
	if err != nil {
		return fmt.Errorf("error loading publishers: %w", err)
	}

	for _, publisher := range publishers {
		fmt.Println("Processing publisher:", publisher.Geofeed)

		// Parse CSV
		rows, comments, invalidEntries, err := parser.ParseCSV(publisher.Geofeed)
		if err != nil {
			fmt.Printf("error parsing CSV: %v\n", err)
			continue
		}

		// Validate entries
		entries, err := geofeed_validation.ValidateAndTuneEntries(rows)
		if err != nil {
			fmt.Printf("error validating entries: %v\n", err)
			continue
		}

		// Metadata summary
		metadata := geofeed_validation.GetMetadataFromEntries(entries, publisher.Geofeed, invalidEntries)

		// Generate HTML report
		err = html_template.GenerateHTMLReport(entries, comments, metadata, publisher.OutputPath())
		if err != nil {
			fmt.Printf("error generating HTML report: %v\n", err)
			continue
		}
	}
	return nil
}

func GeofeedValidation(path string) error {
	fmt.Println("Processing publisher:", path)

	// Parse CSV
	rows, comments, invalidEntries, err := parser.ParseCSV(path)
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
	err = html_template.GenerateHTMLReport(entries, comments, metadata, "")
	if err != nil {
		return fmt.Errorf("error generating HTML report: %w", err)
	}
	return nil
}
