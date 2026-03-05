package main

import (
	"flag"
	"fmt"
	geofeed "ip-geofeed/internal"
	"os"
)

func main() {

	bulk := flag.Bool("bulk", false, "Enable bulk validation mode")
	limitEntries := flag.Int("limit-entries", 0, "Limit the number of entries to validate (0 = no limit)")
	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Println("Usage:")
		fmt.Println("  geofeed-validator <csv-file-or-url>")
		fmt.Println("  geofeed-validator --bulk <file-with-urls>")
		fmt.Println("  geofeed-validator --limit-entries <number> <csv-file-or-url>")
		os.Exit(1)
	}

	input := flag.Arg(0)

	if *bulk {
		err := geofeed.GeofeedsValidation(input, *limitEntries)
		if err != nil {
			fmt.Printf("Error validating geofeeds: %v\n", err)
			os.Exit(1)
		}
	} else {
		err := geofeed.GeofeedValidation(input, *limitEntries)
		if err != nil {
			fmt.Printf("Error validating geofeed: %v\n", err)
			os.Exit(1)
		}
	}

	fmt.Println("Validation complete!")
}
