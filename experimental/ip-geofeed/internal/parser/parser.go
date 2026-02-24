package parser

import (
	"encoding/csv"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

// Row represents a single CSV row
type Row struct {
	Line        int
	IPPrefix    string
	CountryCode string
	RegionCode  string
	City        string
	PostalCode  string
}

// isURL checks if the given string is a valid HTTP/HTTPS URL
func isURL(fileSource string) bool {
	u, err := url.Parse(fileSource)
	return err == nil && (u.Scheme == "http" || u.Scheme == "https")
}

// downloadFile downloads a file from a URL and saves it to the run/data folder
func downloadFile(urlStr string) (string, error) {
	// Create run/data directory if it doesn't exist
	runDataDir := filepath.Join("run", "data")
	if err := os.MkdirAll(runDataDir, 0755); err != nil {
		return "", fmt.Errorf("creating run/data directory: %w", err)
	}

	// Extract filename from URL
	u, err := url.Parse(urlStr)
	if err != nil {
		return "", fmt.Errorf("parsing URL: %w", err)
	}
	filename := filepath.Base(u.Path)
	if filename == "" || filename == "/" {
		filename = "geofeed.csv"
	}

	// Full path where file will be saved
	filepath := filepath.Join(runDataDir, filename)

	// Download the file
	resp, err := http.Get(urlStr)
	if err != nil {
		return "", fmt.Errorf("downloading file from %s: %w", urlStr, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download failed with status %d: %s", resp.StatusCode, urlStr)
	}

	// Create the file
	out, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("creating file %s: %w", filepath, err)
	}
	defer out.Close()

	// Write the response body to file
	if _, err := io.Copy(out, resp.Body); err != nil {
		return "", fmt.Errorf("writing file: %w", err)
	}

	return filepath, nil
}

// resolveFilePath resolves the actual file path, downloading from URL if necessary
func resolveFilePath(fileSource string) (string, error) {
	if isURL(fileSource) {
		fmt.Printf("Downloading from URL: %s\n", fileSource)
		return downloadFile(fileSource)
	}
	// Return local file path as-is
	return fileSource, nil
}

// ParseCSV reads and parses a CSV geofeed file from local path or URL
func ParseCSV(fileSource string) ([]Row, error) {
	// Resolve file path (download from URL if necessary)
	filepath, err := resolveFilePath(fileSource)
	if err != nil {
		return nil, fmt.Errorf("resolving file path: %w", err)
	}

	file, err := os.Open(filepath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	reader := csv.NewReader(file)
	reader.TrimLeadingSpace = true
	reader.FieldsPerRecord = -1

	var rows []Row
	lineNum := 0

	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		lineNum++

		// Skip empty lines and comments
		if len(record) == 0 || (len(record) == 1 && strings.TrimSpace(record[0]) == "") {
			continue
		}
		if len(record) > 0 && strings.HasPrefix(strings.TrimSpace(record[0]), "#") {
			continue
		}

		// Only accept rows with 4 or 5 columns
		if len(record) < 4 || len(record) > 5 {
			continue
		}

		row := Row{
			Line:        lineNum,
			IPPrefix:    strings.TrimSpace(record[0]),
			CountryCode: strings.TrimSpace(record[1]),
			RegionCode:  strings.TrimSpace(record[2]),
			City:        strings.TrimSpace(record[3]),
		}
		if len(record) == 5 {
			row.PostalCode = strings.TrimSpace(record[4])
		}
		rows = append(rows, row)
	}
	return rows, nil
}
