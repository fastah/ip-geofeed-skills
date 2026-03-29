package parser

import (
	"bufio"
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
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

// Record represents a single geofeed entry
type Record struct {
	Geofeed string `json:"geofeed"`
	Inetnum string `json:"inetnum"`
	Source  string `json:"source,omitempty"`
	Netname string `json:"netname,omitempty"`
	Country string `json:"country,omitempty"`
	Org     string `json:"org,omitempty"`
	AdminC  string `json:"admin-c,omitempty"`
	TechC   string `json:"tech-c,omitempty"`
	MntBy   string `json:"mnt-by,omitempty"`
	City    string `json:"city,omitempty"`
}

// Records is a collection of Record entries
type Records []Record

// EncodeInetnum encodes the inetnum field into a filesystem-friendly string
func (p *Record) EncodeInetnum() string {
	s := strings.TrimSpace(p.Inetnum)

	// Convert range separator first
	s = strings.ReplaceAll(s, " - ", "_to_")

	// Replace characters with hyphen
	s = strings.ReplaceAll(s, ".", "-")
	s = strings.ReplaceAll(s, ":", "-")
	s = strings.ReplaceAll(s, "/", "-")

	// Remove unwanted characters (but keep - and _)
	reg := regexp.MustCompile(`[^a-zA-Z0-9\-_]+`)
	s = reg.ReplaceAllString(s, "")

	return s
}

// LoadPublishers reads and unmarshals a publishers.json file
func LoadPublishers(filePath string) (Records, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	var publishers Records
	if err := json.Unmarshal(data, &publishers); err != nil {
		return nil, fmt.Errorf("failed to unmarshal JSON: %w", err)
	}

	return publishers, nil
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
	if filename == "" || filename == "/" || filename == "." {
		filename = "geofeed.csv"
	}

	// Full path where file will be saved
	outputPath := filepath.Join(runDataDir, filename)

	// Create request with headers
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "GET", urlStr, nil)
	if err != nil {
		return "", fmt.Errorf("creating request: %w", err)
	}

	// req.Header.Set("User-Agent", "curl/8.0.0")
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; IPGeofeed/1.0)")
	req.Header.Set("Accept", "*/*")

	client := &http.Client{}

	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("downloading file: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download failed with status %d: %s", resp.StatusCode, urlStr)
	}

	// Create file
	out, err := os.Create(outputPath)
	if err != nil {
		return "", fmt.Errorf("creating file %s: %w", outputPath, err)
	}
	defer out.Close()

	// Copy content
	if _, err := io.Copy(out, resp.Body); err != nil {
		return "", fmt.Errorf("writing file: %w", err)
	}

	return outputPath, nil
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
func ParseCSV(fileSource string, limit int) ([]Row, map[int]string, int, int, error) {
	// Resolve file path (download from URL if necessary)
	filepath, err := resolveFilePath(fileSource)
	if err != nil {
		return nil, nil, 0, 0, fmt.Errorf("resolving file path: %w", err)
	}

	file, err := os.Open(filepath)
	if err != nil {
		return nil, nil, 0, 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)

	var rows []Row
	comments := make(map[int]string)
	lineNum := 0
	invalidEntries := 0
	validEntries := 0
	originalCSVCols := 0

	for scanner.Scan() {
		line := scanner.Text()
		trimmed := strings.TrimSpace(line)
		lineNum++

		// Store empty lines and comments
		if trimmed == "" {
			comments[lineNum] = line
			continue
		}
		if strings.HasPrefix(trimmed, "#") {
			comments[lineNum] = line
			continue
		}

		// Check if we've reached the limit
		if limit > 0 && validEntries >= limit {
			break
		}

		// Parse CSV row from raw line
		reader := csv.NewReader(strings.NewReader(line))
		reader.TrimLeadingSpace = true
		record, err := reader.Read()
		if err != nil {
			continue
		}

		// Accept rows with 1 to 5 columns, pad missing columns with empty strings
		if len(record) < 1 || len(record) > 5 {
			invalidEntries++
			continue
		}

		// Track the maximum number of columns seen across all valid rows
		if len(record) > originalCSVCols {
			originalCSVCols = len(record)
		}

		for len(record) < 4 {
			record = append(record, "")
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
		validEntries++
	}

	if err := scanner.Err(); err != nil {
		return nil, nil, 0, 0, err
	}
	return rows, comments, invalidEntries, originalCSVCols, nil
}
