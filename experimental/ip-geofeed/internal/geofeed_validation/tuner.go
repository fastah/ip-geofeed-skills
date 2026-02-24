package geofeed_validation

// TuneEntry optimizes and applies tuning recommendations for an entry
func TuneEntry(entry *Entry, ctx *ValidationContext) {
	// Apply tuning recommendations if needed
	ProvideTuningRecommendations(entry, ctx)
}

// ProvideTuningRecommendations provides suggestions for optimizing geofeed entries
func ProvideTuningRecommendations(entry *Entry, ctx *ValidationContext) {
	// Check if country is a small territory
	isSmallTerritory := ctx.SmallTerritories[entry.CountryCode]

	// Region specified for small territory
	if isSmallTerritory && entry.RegionCode != "" {
		entry.AddStatusMessage(SuggestRegionUnnecessarySmallTerritory)
	}

	// City specified for small territory
	if isSmallTerritory && entry.City != "" {
		entry.AddStatusMessage(SuggestCityUnnecessarySmallTerritory)
	}

	// Missing region when city is specified (not for small territories)
	if !isSmallTerritory && entry.City != "" && entry.RegionCode == "" {
		entry.AddStatusMessage(SuggestRegionRecommendedWithCity)
	}

	// Unspecified geolocation
	if entry.CountryCode == "" && entry.RegionCode == "" && entry.City == "" {
		entry.AddStatusMessage(SuggestConfirmDoNotGeolocate)
		entry.DoNotGeolocate = true
	}
}
