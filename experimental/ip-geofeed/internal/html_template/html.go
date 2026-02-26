package html_template

import (
	"fmt"
	"html/template"
	"os"

	"ip-geofeed/internal/geofeed_validation"
)

// GenerateHTMLReport generates an HTML validation report from entries
func GenerateHTMLReport(entries []geofeed_validation.Entry) error {
	// Parse the template file
	tmpl, err := template.ParseFiles("internal/html_template/report.html")
	if err != nil {
		return fmt.Errorf("parsing template file: %w", err)
	}

	// Create the data structure to pass to the template
	data := struct {
		Entries []geofeed_validation.Entry
	}{
		Entries: entries,
	}

	// Create output file
	outputFile, err := os.Create("run/output/report.html")
	if err != nil {
		return fmt.Errorf("creating output file: %w", err)
	}
	defer outputFile.Close()

	// Execute the template with the data
	err = tmpl.Execute(outputFile, data)
	if err != nil {
		return fmt.Errorf("executing template: %w", err)
	}

	return nil
}
