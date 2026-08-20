# Migration from `geofeed-tuner`

`tuning-geofeeds` supersedes the legacy `geofeed-tuner` skill.

The public migration removed the legacy skill, experimental implementation, and stale discovery metadata. The two skills are not listed as active alternatives.

The current skill uses a versioned Analysis JSON contract, keeps authored rows and physical lines, separates findings from evidence, limits online data, and requires exact proposal approvals before writing a corrected feed. Legacy reports and generated files do not satisfy this contract.

To migrate:

1. Keep the original geofeed CSV.
2. Install `tuning-geofeeds` from the public repository.
3. Analyze the original CSV again.
4. Review new findings and proposals on their own evidence.
5. Approve exact proposal IDs only after review.
6. Publish only the rechecked full CSV through your normal process.

Nothing is migrated, approved, overwritten, or published automatically.
