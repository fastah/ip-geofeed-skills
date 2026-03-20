package geofeed_validation

import (
	"encoding/json"
	"fmt"
	"ip-geofeed/internal/parser"
	"net"
	"os"
	"regexp"
	"strings"
	"time"
)

var (
	placeholderValues = []string{"undefined", "please select", "null", "n/a", "tbd", "unknown"}
	abbreviatedValues = []string{"la", "frft", "sin01", "lhr", "sin", "maa"}
)

// Country represents an ISO 3166-1 country
type Country struct {
	Alpha2       string `json:"alpha_2"`
	Alpha3       string `json:"alpha_3"`
	Flag         string `json:"flag"`
	Name         string `json:"name"`
	Numeric      string `json:"numeric,omitempty"`
	OfficialName string `json:"official_name,omitempty"`
}

// Region represents an ISO 3166-2 subdivision
type Region struct {
	Code string `json:"code"`
	Name string `json:"name"`
	Type string `json:"type"`
}

// ValidationContext holds all validation data
type ValidationContext struct {
	Countries        map[string]Country
	Regions          map[string]Region
	SmallTerritories map[string]bool
}

// Message represents a validation issue
type Message struct {
	ID      string
	Type    string // ERROR, WARNING, SUGGESTION
	Text    string
	Checked bool
}

// Entry represents a single CSV row with validation results
type Entry struct {
	parser.Row
	Status         string // ERROR, WARNING, SUGGESTION, OK
	Messages       []Message
	HasError       bool
	HasWarning     bool
	HasSuggestion  bool
	IPVersion      string
	DoNotGeolocate bool
	GeocodingHint  string
	Tunable        bool
	TunedEntry     Location
}

// Metadata represents summary information
type Metadata struct {
	InputFile            string
	Timestamp            int64
	TotalEntries         int
	IpV4Entries          int
	IpV6Entries          int
	InvalidEntries       int
	Errors               int
	Warnings             int
	Suggestions          int
	OK                   int
	CityLevelAccuracy    int
	RegionLevelAccuracy  int
	CountryLevelAccuracy int
	DoNotGeolocate       int
}

type Record struct {
	parser.Record
	ReportURL string
}

// Netname represents a grouping of geofeeds by netname
type Netname struct {
	Name     string
	Records  []Record
	TableURL string
}

// RIR represents a Regional Internet Registry with its associated netnames
type RIR struct {
	Name     string
	Netnames map[string]*Netname
}

// RIRCollection represents all Regional Internet Registries
type RIRCollection struct {
	RIRs map[string]*RIR
}

// LoadValidationData loads ISO and territorial data from JSON files
func LoadValidationData() (*ValidationContext, error) {
	ctx := &ValidationContext{
		Countries:        make(map[string]Country),
		Regions:          make(map[string]Region),
		SmallTerritories: make(map[string]bool),
	}

	// Load ISO 3166-1 countries
	countriesFile, err := os.ReadFile("internal/geofeed_validation/iso3166-1.json")
	if err != nil {
		return nil, fmt.Errorf("reading countries file: %w", err)
	}

	var countriesData struct {
		Countries []Country `json:"3166-1"`
	}
	if err := json.Unmarshal(countriesFile, &countriesData); err != nil {
		return nil, fmt.Errorf("parsing countries file: %w", err)
	}

	for _, country := range countriesData.Countries {
		ctx.Countries[country.Alpha2] = country
	}

	// Load ISO 3166-2 regions
	regionsFile, err := os.ReadFile("internal/geofeed_validation/iso3166-2.json")
	if err != nil {
		return nil, fmt.Errorf("reading regions file: %w", err)
	}

	var regionsData struct {
		Regions []Region `json:"3166-2"`
	}
	if err := json.Unmarshal(regionsFile, &regionsData); err != nil {
		return nil, fmt.Errorf("parsing regions file: %w", err)
	}

	for _, region := range regionsData.Regions {
		ctx.Regions[region.Code] = region
	}

	// Load small territories
	territoriesFile, err := os.ReadFile("internal/geofeed_validation/small-territories.json")
	if err != nil {
		return nil, fmt.Errorf("reading small territories file: %w", err)
	}

	var territories []string
	if err := json.Unmarshal(territoriesFile, &territories); err != nil {
		return nil, fmt.Errorf("parsing small territories file: %w", err)
	}

	for _, territory := range territories {
		ctx.SmallTerritories[territory] = true
	}

	return ctx, nil
}

// ValidateEntries validates a list of entries and populates their messages and status
func ValidateEntries(rows []parser.Row) ([]Entry, []Entry, error) {
	// Load validation data
	ctx, err := LoadValidationData()
	if err != nil {
		return nil, nil, fmt.Errorf("error loading validation data: %w", err)
	}
	entries, errEntries := GetEntriesFromServer(rows, ctx)

	// Validate each entry
	for i := range entries {
		ValidateEntry(&entries[i], ctx)
	}
	return entries, errEntries, nil
}

// // ValidateAndTuneEntries validates entries and then applies tuning recommendations
// func ValidateAndTuneEntries(rows []parser.Row) error {
// 	entries, err := ValidateEntries(rows)
// 	if err != nil {
// 		return err
// 	}

// 	// Tune entries based on validation results and geocoding hints
// 	TuneEntries(entries)

// 	return nil
// }

func GetMetadataFromEntries(entries []Entry, inputFile string, invalidEntries int) Metadata {
	metadata := Metadata{
		InputFile:      inputFile,
		Timestamp:      time.Now().UnixMilli(),
		InvalidEntries: invalidEntries,
	}

	for _, entry := range entries {
		metadata.TotalEntries++
		switch entry.IPVersion {
		case "IPv4":
			metadata.IpV4Entries++
		case "IPv6":
			metadata.IpV6Entries++
		}

		if entry.HasError {
			metadata.Errors++
		} else if entry.HasWarning {
			metadata.Warnings++
		} else if entry.HasSuggestion {
			metadata.Suggestions++
		} else {
			metadata.OK++
		}

		if entry.City != "" {
			metadata.CityLevelAccuracy++
		} else if entry.RegionCode != "" {
			metadata.RegionLevelAccuracy++
		} else if entry.CountryCode != "" {
			metadata.CountryLevelAccuracy++
		}

		if entry.DoNotGeolocate {
			metadata.DoNotGeolocate++
		}
	}

	return metadata
}

// ValidateEntry validates a single entry and populates its messages
func ValidateEntry(entry *Entry, ctx *ValidationContext) {
	// 1. IP Prefix validation
	ValidateIPPrefix(entry)

	// 2. Country code validation
	ValidateCountryCode(entry, ctx)

	// 3. Region code validation
	ValidateRegionCode(entry, ctx)

	// 4. City name validation
	ValidateCityName(entry, ctx)

	// 5. Postal code check (deprecated)
	ValidatePostalCode(entry)

	// 6. Tuning recommendations
	ProvideTuningRecommendations(entry, ctx)

	// Determine overall status
	if entry.HasError {
		entry.Status = "ERROR"
	} else if entry.HasWarning {
		entry.Status = "WARNING"
	} else if entry.HasSuggestion {
		entry.Status = "SUGGESTION"
	} else {
		entry.Status = "OK"
	}
}

// LoadRIRData organizes Records into a RIRCollection structure
// by grouping geofeeds by their RIR (Source) and then by netname
func LoadRIRData(publishers parser.Records) *RIRCollection {
	// Create a map to group geofeeds by RIR (Source)
	rirMap := make(map[string]*RIR)

	// Group geofeeds by RIR and then by netname
	for _, record := range publishers {

		if record.Source == "" || record.Netname == "" {
			continue // Skip entries without a source/RIR or netname
		}

		rirName := record.Source

		// Create RIR if it doesn't exist
		if _, exists := rirMap[rirName]; !exists {
			rirMap[rirName] = &RIR{
				Name:     rirName,
				Netnames: make(map[string]*Netname),
			}
		}

		rir := rirMap[rirName]
		netnameKey := record.Netname

		// Create Netname if it doesn't exist
		if _, exists := rir.Netnames[netnameKey]; !exists {
			rir.Netnames[netnameKey] = &Netname{
				Name:    netnameKey,
				Records: []Record{},
			}
		}

		// Add record to the netname
		rir.Netnames[netnameKey].Records = append(rir.Netnames[netnameKey].Records, Record{
			Record:    record,
			ReportURL: "", // This can be populated later with the actual report URL after validation
		})
	}

	return &RIRCollection{
		RIRs: rirMap,
	}
}

// sanitize removes unsafe filesystem characters
func sanitize(s string) string {
	s = strings.TrimSpace(s)
	reg := regexp.MustCompile(`[^a-zA-Z0-9\-_]+`)
	return reg.ReplaceAllString(s, "")
}

func GetSourceTablePath(source string) string {
	if source != "" {
		return strings.ToLower(sanitize(source))
	}
	return ""
}

func GetNetnameTablePath(netname string) string {
	if netname != "" {
		return sanitize(netname)
	}
	return ""
}

// ValidateIPPrefix validates the IP prefix format and properties
func ValidateIPPrefix(entry *Entry) {
	if entry.IPPrefix == "" {
		entry.AddStatusMessage(ErrIPPrefixEmpty)
		return
	}

	// Try to parse as CIDR
	_, ipNet, err := net.ParseCIDR(entry.IPPrefix)
	if err != nil {
		entry.AddStatusMessage(ErrIPPrefixInvalid)
		return
	}

	// Normalize to CIDR notation
	entry.IPPrefix = ipNet.String()
	if ipNet.IP.To4() != nil {
		entry.IPVersion = "IPv4"
	} else {
		entry.IPVersion = "IPv6"
	}

	// Check if it's a public address
	if IsPrivateAddress(ipNet.IP) {
		entry.AddStatusMessage(ErrIPPrefixNonPublic)
		return
	}

	// Check for overly large prefixes
	if entry.IPVersion == "IPv4" {
		ones, _ := ipNet.Mask.Size()
		if ones < 22 {
			entry.AddStatusMessage(SuggestIPv4PrefixLarge)
		}
	} else { // IPv6
		ones, _ := ipNet.Mask.Size()
		if ones < 64 {
			entry.AddStatusMessage(SuggestIPv6PrefixLarge)
		}
	}
}

// IsPrivateAddress checks if an IP is private or reserved
func IsPrivateAddress(ip net.IP) bool {
	if ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsMulticast() {
		return true
	}

	// Check for private IPv4 ranges
	if ip.To4() != nil {
		privateRanges := []string{
			"10.0.0.0/8",
			"172.16.0.0/12",
			"192.168.0.0/16",
			"169.254.0.0/16",
			"127.0.0.0/8",
		}
		for _, cidr := range privateRanges {
			_, ipNet, _ := net.ParseCIDR(cidr)
			if ipNet.Contains(ip) {
				return true
			}
		}
	} else {
		// Check for private IPv6 ranges
		privateRanges := []string{
			"fc00::/7",  // Unique local addresses
			"fe80::/10", // Link-local
			"::1/128",   // Loopback
		}
		for _, cidr := range privateRanges {
			_, ipNet, _ := net.ParseCIDR(cidr)
			if ipNet.Contains(ip) {
				return true
			}
		}
	}

	return false
}

// ValidateCountryCode validates the ISO 3166-1 country code
func ValidateCountryCode(entry *Entry, ctx *ValidationContext) {
	if entry.CountryCode == "" {
		return // Empty is allowed
	}

	if _, exists := ctx.Countries[entry.CountryCode]; !exists {
		entry.AddStatusMessage(ErrCountryCodeInvalid)
	}
}

// ValidateRegionCode validates the ISO 3166-2 region code
func ValidateRegionCode(entry *Entry, ctx *ValidationContext) {
	if entry.RegionCode == "" {
		return // Empty is allowed
	}

	// Check format: COUNTRY-SUBDIVISION
	regionPattern := regexp.MustCompile(`^[A-Z]{2}-[A-Z0-9]{1,3}$`)
	if !regionPattern.MatchString(entry.RegionCode) {
		entry.AddStatusMessage(ErrRegionCodeFormat)
		return
	}

	// Check if region exists in ISO 3166-2
	if _, exists := ctx.Regions[entry.RegionCode]; !exists {
		entry.AddStatusMessage(ErrRegionCodeInvalid)
		return
	}

	// Check if region's country matches the country code
	if entry.CountryCode != "" {
		regionCountry := strings.Split(entry.RegionCode, "-")[0]
		if regionCountry != entry.CountryCode {
			entry.AddStatusMessage(ErrRegionCodeMismatch)
		}
	}
}

// ValidateCityName validates the city name for inconsistencies
func ValidateCityName(entry *Entry, ctx *ValidationContext) {
	if entry.City == "" {
		return // Empty is allowed
	}

	cityLower := strings.ToLower(strings.TrimSpace(entry.City))

	// Check for placeholder values
	for _, placeholder := range placeholderValues {
		if cityLower == placeholder {
			entry.AddStatusMessage(ErrCityPlaceholder)
			return
		}
	}

	// Check for abbreviated values
	for _, abbrev := range abbreviatedValues {
		if cityLower == abbrev {
			entry.AddStatusMessage(ErrCityAbbreviated)
			return
		}
	}

	// Check for inconsistent formatting (very basic heuristic)
	if strings.Contains(entry.City, "  ") || // Double spaces
		(strings.ToUpper(entry.City) == entry.City && len(entry.City) > 3) || // ALL CAPS
		regexp.MustCompile(`[A-Z][a-z]+[A-Z]`).MatchString(entry.City) { // HongKong style
		entry.AddStatusMessage(WarnCityFormattingBad)
	}
}

// ValidatePostalCode checks that postal codes are not included (deprecated by RFC 8805)
func ValidatePostalCode(entry *Entry) {
	if entry.PostalCode != "" {
		entry.AddStatusMessage(ErrPostalCodeDeprecated)
	}
}

func CheckForIsuues(entry *parser.Row, ctx *ValidationContext) bool {
	if entry.CountryCode == "" {
		return false
	}
	if _, exists := ctx.Countries[entry.CountryCode]; exists {
		return true
	}

	if _, exists := ctx.Regions[entry.RegionCode]; entry.RegionCode != "" && exists {
		return true
	}

	return false
}
