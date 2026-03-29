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
	Message string
	Tunable bool
}

// IP Prefix Errors
var (
	IPPrefixEmpty     = ValidationError{ID: "1101", Type: ErrorType, Message: "IP prefix is empty", Tunable: false}
	IPPrefixInvalid   = ValidationError{ID: "1102", Type: ErrorType, Message: "Invalid IP prefix: unable to parse as IPv4 or IPv6 network", Tunable: false}
	IPPrefixNonPublic = ValidationError{ID: "1103", Type: ErrorType, Message: "Non-public IP range is not allowed in an RFC 8805 feed", Tunable: false}
	IPv4PrefixLarge   = ValidationError{ID: "3101", Type: SuggestType, Message: "IPv4 prefix is unusually large and may indicate a typo", Tunable: false}
	IPv6PrefixLarge   = ValidationError{ID: "3102", Type: SuggestType, Message: "IPv6 prefix is unusually large and may indicate a typo", Tunable: false}
)

// Country Code Errors
var (
	ConfirmDoNotGeolocate = ValidationError{ID: "3104", Type: SuggestType, Message: "Confirm whether this subnet is intentionally marked as do-not-geolocate or missing location data", Tunable: true}
	CountryCodeInvalid    = ValidationError{ID: "1201", Type: ErrorType, Message: "Invalid country code: not a valid ISO 3166-1 alpha-2 value", Tunable: true}
)

// Region Code Errors
var (
	RegionCodeFormat                = ValidationError{ID: "1301", Type: ErrorType, Message: "Invalid region format; expected COUNTRY-SUBDIVISION (e.g., US-CA)", Tunable: false}
	RegionCodeInvalid               = ValidationError{ID: "1302", Type: ErrorType, Message: "Invalid region code: not a valid ISO 3166-2 subdivision", Tunable: true}
	RegionCodeMismatch              = ValidationError{ID: "1303", Type: ErrorType, Message: "Region code does not match the specified country code", Tunable: true}
	RegionRecommendedWithCity       = ValidationError{ID: "3303", Type: SuggestType, Message: "Region code is recommended when a city is specified; choose a region from the dropdown", Tunable: true}
	RegionUnnecessarySmallTerritory = ValidationError{ID: "3301", Type: SuggestType, Message: "Region is usually unnecessary for small territories; consider removing the region value", Tunable: true}
)

// City Errors
var (
	CityPlaceholder               = ValidationError{ID: "1401", Type: ErrorType, Message: "Invalid city name: placeholder value is not allowed", Tunable: false}
	CityAbbreviated               = ValidationError{ID: "1402", Type: ErrorType, Message: "Invalid city name: abbreviated or code-based value detected", Tunable: true}
	CityFormattingBad             = ValidationError{ID: "3401", Type: SuggestType, Message: "City name formatting is inconsistent; consider normalizing the value", Tunable: true}
	CityUnnecessarySmallTerritory = ValidationError{ID: "3402", Type: SuggestType, Message: "City-level granularity is usually unnecessary for small territories; consider removing the city value", Tunable: true}
)

// Postal Code Errors
var (
	PostalCodeDeprecated = ValidationError{ID: "1501", Type: ErrorType, Message: "Postal codes are deprecated by RFC 8805 and must be removed for privacy reasons", Tunable: true}
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
