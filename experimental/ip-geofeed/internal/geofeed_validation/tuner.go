package geofeed_validation

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	geofeed_structs "ip-geofeed/internal/geofeed-structs"
	"ip-geofeed/internal/parser"

	"github.com/google/uuid"
)

// ProvideTuningRecommendations provides suggestions for optimizing geofeed entries
func ProvideTuningRecommendations(entry *Entry, ctx *ValidationContext) {
	// Check if country is a small territory
	isSmallTerritory := ctx.SmallTerritories[entry.CountryCode]

	// Region specified for small territory
	if isSmallTerritory && entry.RegionCode != "" {
		entry.AddStatusMessage(RegionUnnecessarySmallTerritory)
	}

	// City specified for small territory
	if isSmallTerritory && entry.City != "" {
		entry.AddStatusMessage(CityUnnecessarySmallTerritory)
	}

	// Missing region when city is specified (not for small territories)
	if !isSmallTerritory && entry.City != "" && entry.RegionCode == "" {
		entry.AddStatusMessage(RegionRecommendedWithCity)
	}

	// Unspecified geolocation
	if entry.CountryCode == "" && entry.RegionCode == "" && entry.City == "" {
		entry.AddStatusMessage(ConfirmDoNotGeolocate)
		entry.DoNotGeolocate = true
	}
}

// callPlaceSearchAPI makes an HTTP POST request to the place-search API
func callPlaceSearchAPI(request *geofeed_structs.InRfc8805RowPlaceSearchBatchParams) ([]geofeed_structs.OutRfc8805RowPlaceResults, error) {
	const apiURL = "https://mcp.fastah.ai/rest/geofeeds/place-search"
	// const apiURL = "http://127.0.0.1:3000/rest/geofeeds/place-search"

	// Marshal the request to JSON
	requestBody, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("marshaling request: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequest("POST", apiURL, bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	// Send the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("sending request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	// Parse the response
	response := geofeed_structs.NewGeofeedPlaceResultsBodyWithDefaults()
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, fmt.Errorf("decoding response: %w", err)
	}

	return response.Results, nil
}

func GetEntriesFromServer(entry_rows []parser.Row, ctx *ValidationContext) ([]Entry, []Entry) {
	const maxBatchSize = 1000 // API limit

	// Build the batch request
	entries := make([]Entry, 0, len(entry_rows))
	rows := geofeed_structs.NewInRfc8805RowPlaceSearchBatchParamsWithDefaults()
	errEntries := make([]Entry, 0)
	deDuplicateMap := make(map[string][]int)
	deDuplicateUUIDMap := make(map[string][]int)

	for i, entry := range entry_rows {
		// If all geolocation fields are empty, set country code to "ZZ" to trigger do-not-geolocate logic in the API
		if entry.CountryCode == "" || strings.ToUpper(entry.CountryCode) == "ZZ" {
			entry.CountryCode = "ZZ"
		}

		key := fmt.Sprintf("%s|%s|%s", entry.CountryCode, entry.RegionCode, entry.City)
		if _, exists := deDuplicateMap[key]; !exists {
			deDuplicateMap[key] = []int{i}
		} else {
			deDuplicateMap[key] = append(deDuplicateMap[key], i)
		}

		entries = append(entries, Entry{
			Row: entry,
		})
	}

	for _, indices := range deDuplicateMap {
		uuid := uuid.New().String()
		deDuplicateUUIDMap[uuid] = indices
	}

	for key, indices := range deDuplicateUUIDMap {
		sampleEntry := entries[indices[0]]
		placeSearchRow := geofeed_structs.NewInRfc8805RowPlaceSearchParams(sampleEntry.CountryCode, key)
		placeSearchRow.SetRegionCode(sampleEntry.RegionCode)
		placeSearchRow.SetCityName(sampleEntry.City)
		rows.Rows = append(rows.Rows, *placeSearchRow)
	}

	// If no entries to process, return early
	if len(rows.Rows) == 0 {
		return entries, errEntries
	}

	// Process in batches of up to 1000 rows
	for batchStart := 0; batchStart < len(rows.Rows); batchStart += maxBatchSize {
		batchEnd := batchStart + maxBatchSize
		if batchEnd > len(rows.Rows) {
			batchEnd = len(rows.Rows)
		}
		batchRows := rows.Rows[batchStart:batchEnd]

		// Call the place-search API for this batch
		request := geofeed_structs.NewInRfc8805RowPlaceSearchBatchParams(batchRows)
		results, err := callPlaceSearchAPI(request)
		if err != nil {
			// Log error but don't fail - just skip tuning for this batch
			fmt.Printf("Warning: Failed to call place-search API for batch %d-%d: %v\n", batchStart, batchEnd, err)
			continue
		}

		// Process results and populate tuned fields
		for _, result := range results {
			// If there's a match, use it to populate tuned fields
			if len(result.Matches) > 0 && !result.IsExplicitlyDoNotGeolocate {
				match := result.Matches[0]

				if hasIssue := CheckForIssues(match.CountryCode, match.StateCode, ctx); hasIssue {
					errEntries = append(errEntries, entries[deDuplicateUUIDMap[result.RowKey][0]])
					continue
				}
				for _, entryIdx := range deDuplicateUUIDMap[result.RowKey] {
					entries[entryIdx].TunedEntry = match
				}
			}

		}
	}
	return entries, errEntries
}
