package main

import (
	"flag"
	"fmt"
	geofeed "ip-geofeed/internal"
	"os"
)

func main() {

	bulk := flag.Bool("bulk", false, "Enable bulk validation mode")
	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Println("Usage:")
		fmt.Println("  geofeed-validator <csv-file-or-url>")
		fmt.Println("  geofeed-validator --bulk <file-with-urls>")
		os.Exit(1)
	}

	input := flag.Arg(0)

	if *bulk {
		err := geofeed.GeofeedsValidation(input)
		if err != nil {
			fmt.Printf("Error validating geofeeds: %v\n", err)
			os.Exit(1)
		}
	} else {
		err := geofeed.GeofeedValidation(input)
		if err != nil {
			fmt.Printf("Error validating geofeed: %v\n", err)
			os.Exit(1)
		}
	}

	fmt.Println("Validation complete!")
}
