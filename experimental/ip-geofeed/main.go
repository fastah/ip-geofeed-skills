package main

import (
	"fmt"
	"os"

	"ip-geofeed/internal/geofeed_validation"
	output "ip-geofeed/internal/html_template"
	"ip-geofeed/internal/parser"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: geofeed-validator <csv-file-or-url>")
		os.Exit(1)
	}

	csvFileSource := os.Args[1]

	// Parse CSV
	rows, err := parser.ParseCSV(csvFileSource)
	if err != nil {
		fmt.Printf("Error parsing CSV: %v\n", err)
		os.Exit(1)
	}

	// Validate entries
	entries, err := geofeed_validation.ValidateEntries(rows)
	if err != nil {
		fmt.Printf("Error validating entries: %v\n", err)
		os.Exit(1)
	}

	// Generate HTML report
	err = output.GenerateHTMLReport(entries)
	if err != nil {
		fmt.Printf("Error generating HTML report: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("Validation complete! Report generated: output.html")
}
