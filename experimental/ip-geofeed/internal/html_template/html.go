package html_template

import (
	"encoding/json"
	"fmt"
	"html/template"
	"os"
	"path/filepath"

	"ip-geofeed/internal/geofeed_validation"
)

// GenerateHTMLReport generates an HTML validation report from entries
func GenerateHTMLReport(entries []geofeed_validation.Entry, comments map[int]string, metadata geofeed_validation.Metadata, path string) error {
	// Parse the template file
	tmpl, err := template.ParseFiles("internal/html_template/report.html")
	if err != nil {
		return fmt.Errorf("parsing template file: %w", err)
	}
	commentsJson, err := json.Marshal(comments)
	if err != nil {
		return fmt.Errorf("marshaling comments to JSON: %w", err)
	}

	// Create the data structure to pass to the template
	data := struct {
		Entries  []geofeed_validation.Entry
		Comments template.JS
		Metadata geofeed_validation.Metadata
	}{
		Entries:  entries,
		Comments: template.JS(commentsJson),
		Metadata: metadata,
	}

	// Extract directory
	filePath := filepath.Join("run", "output", path)
	dirPath := filepath.Dir(filePath)

	// Create directories if they don't exist
	err = os.MkdirAll(dirPath, 0755)
	if err != nil {
		return fmt.Errorf("creating output directory: %w", err)
	}

	outputFile, err := os.Create(filePath)
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

func GenerateNetnameHTMLTable(records geofeed_validation.Netname, path string) error {
	// Parse the template file
	tmpl, err := template.ParseFiles("internal/html_template/netname_table.html")
	if err != nil {
		return fmt.Errorf("parsing template file: %w", err)
	}

	// Create the data structure to pass to the template
	data := struct {
		Records []geofeed_validation.Record
	}{
		Records: records.Records,
	}

	// Extract directory
	filePath := filepath.Join("run", "output", path)
	dirPath := filepath.Dir(filePath)

	// Create directories if they don't exist
	err = os.MkdirAll(dirPath, 0755)
	if err != nil {
		return fmt.Errorf("creating output directory: %w", err)
	}

	outputFile, err := os.Create(filePath)
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
