package parser

import (
	"bufio"
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

// Publisher represents a single publisher entry
type Publisher struct {
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

// Publishers is a collection of Publisher entries
type Publishers []Publisher

// EncodeInetnum encodes the inetnum field into a filesystem-friendly string
func (p *Publisher) EncodeInetnum() string {
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

// sanitizeFolder removes unsafe filesystem characters
func sanitizeFolder(s string) string {
	s = strings.TrimSpace(s)
	reg := regexp.MustCompile(`[^a-zA-Z0-9\-_]+`)
	return reg.ReplaceAllString(s, "")
}

func (p *Publisher) OutputPath() string {
	var parts []string

	if p.Source != "" {
		parts = append(parts, sanitizeFolder(p.Source))
	}

	if p.Org != "" {
		parts = append(parts, sanitizeFolder(p.Org))
	}

	if p.Netname != "" {
		parts = append(parts, sanitizeFolder(p.Netname))
	}

	parts = append(parts, p.EncodeInetnum())

	return filepath.Join(parts...)
}

// LoadPublishers reads and unmarshals a publishers.json file
func LoadPublishers(filePath string) (Publishers, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	var publishers Publishers
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
func ParseCSV(fileSource string) ([]Row, map[int]string, int, error) {
	// Resolve file path (download from URL if necessary)
	filepath, err := resolveFilePath(fileSource)
	if err != nil {
		return nil, nil, 0, fmt.Errorf("resolving file path: %w", err)
	}

	file, err := os.Open(filepath)
	if err != nil {
		return nil, nil, 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)

	var rows []Row
	comments := make(map[int]string)
	lineNum := 0
	invalidEntries := 0

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

		// Parse CSV row from raw line
		reader := csv.NewReader(strings.NewReader(line))
		reader.TrimLeadingSpace = true
		record, err := reader.Read()
		if err != nil {
			continue
		}

		// Only accept rows with 4 or 5 columns
		if len(record) < 4 || len(record) > 5 {
			invalidEntries++
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

	if err := scanner.Err(); err != nil {
		return nil, nil, 0, err
	}
	return rows, comments, invalidEntries, nil
}
