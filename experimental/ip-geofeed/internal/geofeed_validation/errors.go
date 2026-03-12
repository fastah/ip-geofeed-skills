package geofeed_validation

// ErrorType represents the type of validation message
const (
	ErrorType   = "ERROR"
	WarningType = "WARNING"
	SuggestType = "SUGGESTION"
)

// ValidationError defines a structured error/warning/suggestion
type ValidationError struct {
	ID      string
	Type    string
	Field   string
	Message string
	Tunable bool
}

// IP Prefix Errors
var (
	ErrIPPrefixEmpty       = ValidationError{ID: "1101", Type: ErrorType, Field: "ip_prefix", Message: "IP prefix is empty", Tunable: false}
	ErrIPPrefixInvalid     = ValidationError{ID: "1102", Type: ErrorType, Field: "ip_prefix", Message: "Invalid IP prefix: unable to parse as IPv4 or IPv6 network", Tunable: false}
	ErrIPPrefixNonPublic   = ValidationError{ID: "1103", Type: ErrorType, Field: "ip_prefix", Message: "Non-public IP range is not allowed in an RFC 8805 feed", Tunable: false}
	SuggestIPv4PrefixLarge = ValidationError{ID: "3101", Type: SuggestType, Field: "ip_prefix", Message: "IPv4 prefix is unusually large and may indicate a typo", Tunable: false}
	SuggestIPv6PrefixLarge = ValidationError{ID: "3102", Type: SuggestType, Field: "ip_prefix", Message: "IPv6 prefix is unusually large and may indicate a typo", Tunable: false}
)

// Country Code Errors
var (
	ErrCountryCodeInvalid = ValidationError{ID: "1201", Type: ErrorType, Field: "country_code", Message: "Invalid country code: not a valid ISO 3166-1 alpha-2 value", Tunable: true}
)

// Region Code Errors
var (
	ErrRegionCodeFormat   = ValidationError{ID: "1301", Type: ErrorType, Field: "region_code", Message: "Invalid region format; expected COUNTRY-SUBDIVISION (e.g., US-CA)", Tunable: false}
	ErrRegionCodeInvalid  = ValidationError{ID: "1302", Type: ErrorType, Field: "region_code", Message: "Invalid region code: not a valid ISO 3166-2 subdivision", Tunable: true}
	ErrRegionCodeMismatch = ValidationError{ID: "1303", Type: ErrorType, Field: "region_code", Message: "Region code does not match the specified country code", Tunable: true}
)

// City Errors
var (
	ErrCityPlaceholder    = ValidationError{ID: "1401", Type: ErrorType, Field: "city", Message: "Invalid city name: placeholder value is not allowed", Tunable: false}
	ErrCityAbbreviated    = ValidationError{ID: "1402", Type: ErrorType, Field: "city", Message: "Invalid city name: abbreviated or code-based value detected", Tunable: true}
	WarnCityFormattingBad = ValidationError{ID: "2401", Type: WarningType, Field: "city", Message: "City name formatting is inconsistent; consider normalizing the value", Tunable: true}
)

// Postal Code Errors
var (
	ErrPostalCodeDeprecated = ValidationError{ID: "1501", Type: ErrorType, Field: "postal_code", Message: "Postal codes are deprecated by RFC 8805 and must be removed for privacy reasons", Tunable: true}
)

// Suggestions
var (
	SuggestRegionUnnecessarySmallTerritory = ValidationError{ID: "3301", Type: SuggestType, Field: "region_code", Message: "Region is usually unnecessary for small territories; consider removing the region value", Tunable: true}
	SuggestCityUnnecessarySmallTerritory   = ValidationError{ID: "3402", Type: SuggestType, Field: "city", Message: "City-level granularity is usually unnecessary for small territories; consider removing the city value", Tunable: true}
	SuggestRegionRecommendedWithCity       = ValidationError{ID: "3303", Type: SuggestType, Field: "region_code", Message: "Region code is recommended when a city is specified; choose a region from the dropdown", Tunable: true}
	SuggestConfirmDoNotGeolocate           = ValidationError{ID: "3104", Type: SuggestType, Field: "ip_prefix", Message: "Confirm whether this subnet is intentionally marked as do-not-geolocate or missing location data", Tunable: true}
)

func (e *Entry) AddStatusMessage(msg ValidationError) {
	e.Messages = append(e.Messages, Message{
		ID:      msg.ID,
		Type:    msg.Type,
		Text:    msg.Message,
		Checked: msg.Tunable,
	})

	e.Tunable = e.Tunable || msg.Tunable
	switch msg.Type {
	case ErrorType:
		e.HasError = true
	case WarningType:
		e.HasWarning = true
	case SuggestType:
		e.HasSuggestion = true
	}
}
