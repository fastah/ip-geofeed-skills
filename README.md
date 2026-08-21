# Fastah NetOps Tools

Fastah NetOps Tools helps you check a public IP geofeed, decide what to fix, recheck the result, and prepare the full feed for your normal publication process.

The `tuning-geofeeds` skill works with [RFC 8805](https://www.rfc-editor.org/rfc/rfc8805.html) CSV feeds. It keeps your source file unchanged. It explains what needs attention and creates proposals when you ask. You choose every change. It never silently overwrites or publishes a feed.

## Get the feed

Claude Cowork, other cloud agents, and corporate networks may block some HTTPS downloads. If the host cannot fetch your feed URL, upload the CSV. This is the intended path. Do not ask the agent to bypass the host's network policy or reconstruct rows.

## What it does not do

- It does not manage private IP address plans.
- It does not decide where your network should be located.
- It does not prove ownership of address space.
- It does not upload or publish a feed for you.

## What you need

| Item | Current support |
|---|---|
| Python | 3.14 or newer |
| Input | A local, strict UTF-8 RFC 8805 CSV file |
| Amp | Published from this public repository; the complete repository install has passed an isolated Amp smoke test |
| Claude and OpenAI marketplaces | Not published yet. Do not treat generated review packages as listings. |
| Internet access | Not needed for the standard offline report |
| Optional online checks | Direct registry checks and Fastah place search, only after you agree |

Install the complete skill in Amp:

```bash
amp skill add --overwrite https://github.com/fastah/ip-geofeed-skills.git
```

Then ask Amp to use `tuning-geofeeds`, or start with the first prompt below. The packaged repository layout is checked with a real isolated Amp installation.

## Check a local feed in five minutes

Keep the original CSV. Work on copies and new output files.

### 1. Run an offline check

Attach or name the local file, then ask:

> Analyze `/path/to/geofeed.csv` as a public RFC 8805 geofeed. Keep the source unchanged. Work offline. Create Analysis JSON, a Markdown summary, an offline HTML dashboard, and GeoJSON.

Start with Markdown for a quick review. Open the HTML dashboard when you need row filters and linked evidence. Keep the Analysis JSON: it is the complete, machine-readable record used to create every report. Its `source.sha256` value supports audits and binds later approvals to the analyzed file. You do not normally need to calculate another digest.

### 2. Understand what needs attention

Ask:

> Show the errors first. Separate RFC violations, Fastah recommendations, and operational evidence. Explain each affected source row and prefix relationship in plain words.

Nothing has changed yet. The reports describe the source you supplied.

### 3. Ask for proposals when you are ready

> Propose conservative corrections. Show each proposal ID, old value, new value, rule, and reason. Do not apply anything.

Review every proposal. Reply with `approve` or `reject` for each exact proposal ID. No decision is assumed.

### 4. Export and recheck

After you approve at least one proposal, ask:

> Export the approved corrections to a new full CSV. Keep the original file. Reanalyze the corrected CSV and show any remaining findings.

The export contains the complete feed, not a patch. Compare the new report with the original report before publication.

### 5. Publish through your normal process

The tool stops at a verified local file. Use your normal web, registry, change-control, and rollback process to publish it. See [Publish the checked feed](#publish-the-checked-feed).

## Three kinds of finding

| Class | Meaning | What to do |
|---|---|---|
| RFC violation | The row conflicts with an RFC 8805 format or feed rule. | Fix it before publication, or record why you cannot. |
| Fastah recommendation | The row is valid, but a public-feed quality check found a risk. | Review it with your network knowledge. |
| Operational evidence | Prefix relationships, RDAP, or place-search results add context. | Treat it as evidence, not an automatic correction. |

Severity and class are separate. An informational finding can still be useful. A warning is not proof that the source is wrong.

## Prefix relationships

The report links related rows so you can review them together.

| Model term | Practical meaning | Example |
|---|---|---|
| `duplicate` | The same effective prefix and location entry appears again. | Two identical `203.0.113.0/24` rows. |
| `equal` | Two authored entries normalize to the same prefix. | Two forms of the same canonical `/24`. |
| `parent` | A broader row contains a more specific row. | A `/16` contains a `/24`. |
| `carved_child` | The more specific row inside a parent. | The contained `/24` viewed from the child row. |
| `overlap` | Rows share address space not already described by a more specific relationship. | Review both rows to see which entry should control the shared space. |
| `conflicting_geolocation` | Equal normalized prefixes carry different normalized locations. | The same `/24` names two cities. |

Parent and child rows can be intentional. Equal prefixes with different locations need attention. The relationship itself never changes a row.

## Files and privacy

All local artifacts stay in the work directory you choose until you delete or share them. Fastah does not automatically upload or publish them.

| Artifact | Use | Where it stays and what can leave |
|---|---|---|
| Original CSV | Source evidence and rollback point | Local. It is never overwritten. |
| Analysis JSON | Complete typed record of rows, findings, relationships, and optional evidence | Local. It can contain prefixes, source values, and retained physical lines. |
| Markdown | Fast review and change discussion | Local unless you share it. It can name prefixes and findings. |
| Offline HTML | Searchable dashboard with the Analysis data embedded | Local unless you share it. It contains the full report and can be large. |
| GeoJSON | Map data from MCP place evidence | Local unless you share it. Offline or registry-only analysis produces a valid empty FeatureCollection and an informational CLI message; no geometry is invented. |
| Correction plan and approval | Exact proposals and your decisions | Local. They bind decisions to the source and analysis. |
| Corrected CSV | Full approved feed for your publication process | Local until you publish it. Publication is always manual. |
| Registry request | Optional authority-consistency check | The canonical prefix goes directly to the authoritative registry selected through current bootstrap data. |
| Place-search request batches | Optional online place check | Only `rowKey`, `countryCode`, `regionCode`, `cityName`, and `searchMode` go to Fastah. |
| Place-search mapping and captures | Join each result back to local rows and retain an audit trail | Local. The mapping is never sent to Fastah and contains no prefixes. |

## Optional registry check

The skill asks before using the Registration Data Access Protocol (RDAP). It sends canonical prefixes directly to the authoritative Regional Internet Registry selected through current Internet Assigned Numbers Authority bootstrap data. It does not send them to Fastah's place-search service.

The result is one of `consistent`, `conflicting`, `unverified`, or `unavailable`. These labels compare limited public registration evidence with an optional profile. They do not prove legal ownership. A timeout or unavailable registry does not stop the offline report.

## Optional Fastah place search

Fastah's Model Context Protocol (MCP) service is optional and online. It uses host-managed OAuth. The skill asks first. The host must have a verified production connection. It discovers the tool and its current batch limit before sending any rows.

When this stage runs, every valid source row eligible for MCP receives one normalized typed result:

| Status | Meaning |
|---|---|
| `matched` | Place evidence was found. It remains advisory. |
| `do_not_geolocate` | An empty or `ZZ` country intentionally asks consumers not to geolocate the prefix. It uses the common result format and does not run a database lookup. |
| `no_match` | No suitable place evidence was found. |
| `invalid_input` | The place-search input was not valid for the service. |
| `backend_unavailable` | The service could not complete that row. It may be retryable. |

Only `rowKey`, `countryCode`, `regionCode`, `cityName`, and `searchMode` cross the Fastah MCP boundary. `rowKey` is an opaque, batch-unique correlation key and is echoed unchanged. Prefixes, the feed, comments, Analysis JSON, RDAP data, publisher details, proposals, and approvals do not. Exact repeated place queries are sent once and safely fanned back to their source rows. If MCP is unavailable, keep working with the offline report.

Fastah MCP service logs are separate from your local artifacts. The release policy allows only sanitized request metadata and aggregate outcomes, not tokens, row location contents, feeds, Analysis JSON, RDAP data, publisher data, approvals, or raw backend errors. It requires deletion after 30 days. Production log fields and deletion controls still need live verification before release.

## Limits and troubleshooting

| Situation | What happens | First response |
|---|---|---|
| Up to 400,000 data rows | The complete feed can be analyzed. Comments and blank lines do not count. | Keep the complete source and review the output sizes. |
| More than 400,000 data rows | Analysis stops before creating partial Analysis JSON. Nothing is truncated. | Do not split the feed to hide the limit. Reduce scope only through your normal source-management process. |
| Invalid UTF-8 | Local analysis stops with an encoding error. | Keep the original file. Save a separate verified UTF-8 working copy. |
| Remote feed URL | Download is owned by the host, not this package. Allowlisted networks may block it. | Use the host's normal download capability. If unavailable, upload the CSV. Do not bypass network policy or reconstruct it. |
| Empty GeoJSON | The valid FeatureCollection has no features when no MCP place evidence supplies usable coordinates or bounds. | Use Markdown and Analysis JSON for offline findings. Run optional MCP only after agreeing to its privacy boundary. RDAP does not populate GeoJSON. |
| Declared non-UTF-8 source | The analyzer does not silently convert it. | For a response such as `Content-Type: text/csv; charset=ISO-8859-1`, keep the raw file and create a separate strict UTF-8 copy with both digests. LACNIC has been observed using this pattern; do not special-case a hostname. |
| Prefix has host bits | The authored CIDR is retained but marked invalid. | Confirm the intended network address. Do not accept automatic masking without checking the allocation. |
| Country or region code is invalid | The row is retained with a finding. | Check the intended ISO country and subdivision code. Empty or `ZZ` country has a separate do-not-geolocate meaning. |
| Output file already exists | The command refuses to overwrite it. | Choose a new output name. Keep the earlier artifact for comparison. |
| RDAP or MCP partly fails | Typed unavailable results remain beside successful results. | Continue offline. Retry only the optional stage when appropriate. |
| Large HTML report | It can take time and memory to generate and open. | Use Markdown and Analysis JSON first. In review, feeds near 51,000 and 53,000 rows produced HTML around 225 MB, took over three minutes to generate, and took about 14 seconds to build the browser document. The 400,000-row input limit is not an acceptable browser-performance budget. |

## Publish the checked feed

Fastah NetOps Tools does not publish for you. Use this checklist with your normal change process:

1. Reanalyze the corrected full CSV. Resolve or accept every remaining finding through your own review.
2. Confirm that the publication copy is UTF-8 CSV and contains the intended complete prefix set.
3. Put the file at a stable HTTPS URL. Serve the CSV body directly, without a login page or HTML wrapper. Use `text/csv` where your web server supports it. Set sensible HTTP cache information for collectors.
4. Coordinate with your Regional, National, or Local Internet Registry—or your provider—for the relevant `inetnum` and `inet6num` objects. Under [RFC 9632](https://www.rfc-editor.org/rfc/rfc9632.html), prefer one `geofeed:` HTTPS reference where the registry supports it. Where it does not, use the exact case-sensitive `remarks: Geofeed https://...` form.
5. If you use the optional RFC 9632 Resource Public Key Infrastructure (RPKI) signature, follow your RPKI process and update the signature when the file or signing certificate changes. This tool does not sign the feed.
6. Fetch the published URL as a collector would. Confirm status, bytes, encoding, and access from outside your network.
7. Monitor the URL and registry reference. Keep the previous known-good file and rollback steps.

RFC 8805 consumers treat a feed as a hint and may refresh it on their own schedule. Publication does not guarantee when or whether a provider will use a change.

## Versions and help

- Skill and plugin: `0.2.0`
- Analyzer and Analysis schema: `0.5.0` / `0.5.0`
- MCP response contract: `1.0`

These versions move independently. Include them with the source digest when you report a problem.

- Website: [https://getfastah.com/](https://getfastah.com/)
- Support: [support@getfastah.com](mailto:support@getfastah.com)
- [Privacy policy](https://www.iubenda.com/privacy-policy/40053234)
- [Terms of use](https://mcp.fastah.ai/terms-of-use.txt)
- [Maintainer and release instructions](CONTRIBUTING.md)
- [Migration from `geofeed-tuner`](MIGRATION.md)
