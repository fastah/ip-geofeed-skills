from dataclasses import dataclass

# ErrorType constants
ERROR_TYPE = "ERROR"
WARNING_TYPE = "WARNING"
SUGGEST_TYPE = "SUGGESTION"


@dataclass
class ValidationError:
    """Defines a structured error/warning/suggestion."""
    id: str
    type: str
    field: str
    message: str
    tunable: bool


# IP Prefix Errors
ERR_IP_PREFIX_EMPTY = ValidationError(
    id="1101", type=ERROR_TYPE, field="ip_prefix",
    message="IP prefix is empty", tunable=False,
)
ERR_IP_PREFIX_INVALID = ValidationError(
    id="1102", type=ERROR_TYPE, field="ip_prefix",
    message="Invalid IP prefix: unable to parse as IPv4 or IPv6 network", tunable=False,
)
ERR_IP_PREFIX_NON_PUBLIC = ValidationError(
    id="1103", type=ERROR_TYPE, field="ip_prefix",
    message="Non-public IP range is not allowed in an RFC 8805 feed", tunable=False,
)
SUGGEST_IPV4_PREFIX_LARGE = ValidationError(
    id="3101", type=SUGGEST_TYPE, field="ip_prefix",
    message="IPv4 prefix is unusually large and may indicate a typo", tunable=False,
)
SUGGEST_IPV6_PREFIX_LARGE = ValidationError(
    id="3102", type=SUGGEST_TYPE, field="ip_prefix",
    message="IPv6 prefix is unusually large and may indicate a typo", tunable=False,
)

# Country Code Errors
ERR_COUNTRY_CODE_INVALID = ValidationError(
    id="1201", type=ERROR_TYPE, field="country_code",
    message="Invalid country code: not a valid ISO 3166-1 alpha-2 value", tunable=True,
)

# Region Code Errors
ERR_REGION_CODE_FORMAT = ValidationError(
    id="1301", type=ERROR_TYPE, field="region_code",
    message="Invalid region format; expected COUNTRY-SUBDIVISION (e.g., US-CA)", tunable=False,
)
ERR_REGION_CODE_INVALID = ValidationError(
    id="1302", type=ERROR_TYPE, field="region_code",
    message="Invalid region code: not a valid ISO 3166-2 subdivision", tunable=True,
)
ERR_REGION_CODE_MISMATCH = ValidationError(
    id="1303", type=ERROR_TYPE, field="region_code",
    message="Region code does not match the specified country code", tunable=True,
)

# City Errors
ERR_CITY_PLACEHOLDER = ValidationError(
    id="1401", type=ERROR_TYPE, field="city",
    message="Invalid city name: placeholder value is not allowed", tunable=False,
)
ERR_CITY_ABBREVIATED = ValidationError(
    id="1402", type=ERROR_TYPE, field="city",
    message="Invalid city name: abbreviated or code-based value detected", tunable=True,
)
WARN_CITY_FORMATTING_BAD = ValidationError(
    id="2401", type=WARNING_TYPE, field="city",
    message="City name formatting is inconsistent; consider normalizing the value", tunable=True,
)

# Postal Code Errors
ERR_POSTAL_CODE_DEPRECATED = ValidationError(
    id="1501", type=ERROR_TYPE, field="postal_code",
    message="Postal codes are deprecated by RFC 8805 and must be removed for privacy reasons", tunable=True,
)

# Suggestions
SUGGEST_REGION_UNNECESSARY_SMALL_TERRITORY = ValidationError(
    id="3301", type=SUGGEST_TYPE, field="region_code",
    message="Region is usually unnecessary for small territories; consider removing the region value", tunable=True,
)
SUGGEST_CITY_UNNECESSARY_SMALL_TERRITORY = ValidationError(
    id="3402", type=SUGGEST_TYPE, field="city",
    message="City-level granularity is usually unnecessary for small territories; consider removing the city value", tunable=True,
)
SUGGEST_REGION_RECOMMENDED_WITH_CITY = ValidationError(
    id="3303", type=SUGGEST_TYPE, field="region_code",
    message="Region code is recommended when a city is specified; choose a region from the dropdown", tunable=True,
)
SUGGEST_CONFIRM_DO_NOT_GEOLOCATE = ValidationError(
    id="3104", type=SUGGEST_TYPE, field="ip_prefix",
    message="Confirm whether this subnet is intentionally marked as do-not-geolocate or missing location data", tunable=True,
)
