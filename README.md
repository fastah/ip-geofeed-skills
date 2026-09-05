# Fastah NetOps Tools

**Check a public IP geofeed, see what's worth fixing, fix only what you approve, and get it ready to publish — without ever silently changing your file.**

The `tuning-geofeeds` skill reads an [RFC 8805](https://www.rfc-editor.org/rfc/rfc8805.html) geofeed CSV and tells you, in plain words, what's solid and what needs a look. It keeps your source file untouched. It proposes changes only when you ask, and you approve every single one. It never overwrites your feed and never publishes for you.

Works in **Claude** (Cowork / desktop) and **Amp**. Same skill, same guarantees.

---

## Quickstart (60 seconds)

1. Get the skill into your agent (see [Install](#install)).
2. Give it your feed — a local file or an attachment.
3. Ask: *"Analyze this as a public RFC 8805 geofeed, offline. Give me the Markdown summary, the HTML dashboard, and GeoJSON."*
4. Read the summary. If anything's worth fixing, ask for proposals, approve the ones you want, and export a corrected CSV.

That's the whole loop. Everything below is detail for when you want it.

---

## What it does — and doesn't

**It does:** parse and validate your feed, flag RFC violations and quality risks, map out how your prefixes relate (parents, carved children, overlaps, conflicts), optionally cross-check registration (RDAP) and place names (Fastah), and — only on your say-so — write a corrected full CSV and re-check it.

**It doesn't:**
- manage private/internal IP plans,
- decide where your network *should* be,
- prove ownership of address space,
- or upload/publish anything for you.

Your original file is evidence and rollback point. It's never overwritten.

---

## Install

### In Claude (Cowork / desktop)

You have two ways in:

**A. Install the plugin** (recommended — brings the skill *and* the optional Fastah place-search MCP together).
Add this repo as a plugin source in your Claude desktop app, then enable **Fastah NetOps Tools**. The bundled `.mcp.json` wires up the optional `fastah-netops` place-search service (host-managed sign-in; see [Optional Fastah place search](#optional-fastah-place-search)).

**B. Point Claude at this repo** and ask it to use the `tuning-geofeeds` skill directly. Claude will clone it and run the analyzer.

> **You'll need Python 3.14 (final).** The analyzer requires it and, on purpose, **rejects release candidates** (`3.14.0rc2` won't do — you need `3.14.0` or newer final). Most hosts don't ship 3.14 yet. The fastest way in is `uv`:
>
> ```bash
> uv python install 3.14      # needs a recent uv that resolves 3.14 *final*, not rc
> uv python find 3.14         # note the path it prints
> ```
>
> If your `uv` only offers `3.14.0rcN`, upgrade `uv` first — older builds predate the 3.14 final manifest. Then let the skill bootstrap itself:
>
> ```bash
> "<python3.14>" scripts/geofeed_cli.py --bootstrap "<your-work-dir>"
> # prints PYTHON=… — use that interpreter for every later command
> ```

### In Amp

```bash
amp skill add --overwrite https://github.com/fastah/ip-geofeed-skills.git
```

Then ask Amp to use `tuning-geofeeds`.

---

## Getting your feed to the agent

Some AI hosts and corporate networks only allow downloads from an allowlist, so the agent may not be able to fetch your feed's URL directly. **That's expected — don't ask it to work around your network policy or rebuild the feed from memory.** Instead:

- **In Claude:** just **attach the CSV to the chat.** The agent reads it from your uploads. (If a folder on your machine is connected, it can read it from there too.)
- **In Amp / CLI hosts:** name the local file path, or use the host's normal download capability.

If you paste a URL and the agent says it's blocked, uploading the file is the intended path, not a failure.

---

## Check a local feed in five minutes

Keep the original CSV. Work on copies and new output files.

### 1. Run an offline check

Attach or name the local file, then ask:

> Analyze `/path/to/geofeed.csv` as a public RFC 8805 geofeed. Keep the source unchanged. Work offline. Create Analysis JSON, a Markdown summary, an offline HTML dashboard, and GeoJSON.

Start with the Markdown for a quick read. Open the HTML dashboard when you want row filters and linked evidence. Keep the Analysis JSON — it's the complete machine-readable record behind every report, and its `source.sha256` binds later approvals to exactly the file you analyzed.

### 2. Understand what needs attention

> Show the errors first. Separate RFC violations, Fastah recommendations, and operational evidence. Explain each affected row and prefix relationship in plain words.

Nothing has changed. The reports just describe what you gave it.

### 3. Ask for proposals when you're ready

> Propose conservative corrections. Show each proposal ID, old value, new value, rule, and reason. Don't apply anything.

Review every proposal and reply `approve` or `reject` for each exact ID. Nothing is assumed.

### 4. Export and recheck

> Export the approved corrections to a new full CSV. Keep the original. Reanalyze the corrected CSV and show any remaining findings.

The export is the complete feed, not a patch. Compare old vs. new before you publish.

### 5. Publish through your normal process

The tool stops at a verified local file. Use your own web, registry, change-control, and rollback process — see [Publish the checked feed](#publish-the-checked-feed).

---

## What to expect when the online checks can't run

The offline report needs no internet and is the whole story for most feeds. The two **optional** online stages depend on your host's network:

- **RDAP** talks directly to the Regional Internet Registries. If your host blocks that egress, every prefix comes back `unavailable` and the base findings stand — that's the tool failing *safely*, not a broken run. (Heads-up: if RDAP finishes in ~0 seconds for a large feed, it didn't succeed instantly — every query was blocked. Check whether RIR egress is allowed on your host.)
- **Fastah place search** runs over an MCP service at `mcp.fastah.ai`. If that host isn't on your org's egress allowlist, the stage can't send anything — and that includes some managed AI hosts where *both* the agent and its tool sandbox sit behind the same proxy. If you want this stage, ask your admin to allowlist **`mcp.fastah.ai`**.

Either way, the offline analysis is complete and correct on its own. The online stages add evidence (place plausibility, registration consistency, map geometry) — they never change the pass/fail verdict.

---

## Three kinds of finding

| Class | Meaning | What to do |
|---|---|---|
| RFC violation | The row breaks an RFC 8805 format or feed rule. | Fix before publication, or record why you can't. |
| Fastah recommendation | The row is valid, but a public-feed quality check found a risk. | Review with your network knowledge. |
| Operational evidence | Prefix relationships, RDAP, or place-search results add context. | Treat as evidence, not an automatic fix. |

Severity and class are separate. An informational finding can still be useful. A warning isn't proof the source is wrong.

---

## Prefix relationships

The report links related rows so you can review them together.

| Model term | Practical meaning | Example |
|---|---|---|
| `duplicate` | The same effective prefix and location appears again. | Two identical `203.0.113.0/24` rows. |
| `equal` | Two authored entries normalize to the same prefix. | Two forms of the same canonical `/24`. |
| `parent` | A broader row contains a more specific row. | A `/16` contains a `/24`. |
| `carved_child` | The more specific row inside a parent. | The contained `/24`, seen from the child. |
| `overlap` | Rows share space not already described by a more specific relationship. | Review both to see which should control it. |
| `conflicting_geolocation` | Equal normalized prefixes carry different locations. | The same `/24` names two cities. |

Parent/child rows can be intentional. Equal prefixes with different locations need attention. The relationship itself never changes a row.

---

## Files and privacy

Everything stays in the work directory you choose until you delete or share it. Fastah never auto-uploads or publishes it.

| Artifact | Use | Where it stays / what can leave |
|---|---|---|
| Original CSV | Source evidence and rollback point | Local. Never overwritten. |
| Analysis JSON | Complete typed record of rows, findings, relationships, and evidence | Local. Can contain prefixes, source values, retained physical lines. |
| Markdown | Fast review and discussion | Local unless you share it. Can name prefixes and findings. |
| Offline HTML | Searchable dashboard with the data embedded | Local unless you share it. Full report; can be large. |
| GeoJSON | One feature per prefix row: geography, depth, finding summaries, ASN/org/routing associations, MCP H3 cells, and place geometry when available | Local unless you share it. Geometry is null without MCP place evidence; none is invented. |
| Correction plan + approval | Exact proposals and your decisions | Local. Bind decisions to the source and analysis. |
| Corrected CSV | Full approved feed for your publication process | Local until you publish it. Publication is always manual. |
| Registry request | Optional authority-consistency check | The canonical prefix goes directly to the authoritative registry via current bootstrap data. |
| Place-search request batches | Optional online place check | Only `rowKey`, `countryCode`, `regionCode`, `cityName`, `searchMode` go to Fastah. |
| Place-search mapping + captures | Join results back to local rows; audit trail | Local. The mapping is never sent to Fastah and contains no prefixes. |

---

## Optional registry check (RDAP)

The skill asks before using RDAP. It sends canonical prefixes directly to the authoritative Regional Internet Registry (selected via current IANA bootstrap data), **not** to Fastah's place-search service.

The result is `consistent`, `conflicting`, `unverified`, or `unavailable`. These compare limited public registration evidence against an optional publisher profile. They **don't** prove legal ownership. A timeout or unreachable registry doesn't stop the offline report — it's recorded as `unavailable`.

> A publisher profile (org name + ASN, e.g. `{"organization_name":"Example Networks","asn":"AS64500"}`) makes the assessment meaningful. Without one, results normally stay `unverified` — that's expected, not an error.

---

## Optional Fastah place search

Fastah's Model Context Protocol (MCP) service is optional and online, at `mcp.fastah.ai`. It uses host-managed sign-in. The skill asks first and checks the tool's current batch limit before sending any rows.

When it runs, every eligible row gets one normalized typed result:

| Status | Meaning |
|---|---|
| `matched` | Place evidence was found. Advisory. |
| `do_not_geolocate` | Empty or `ZZ` country intentionally asks consumers not to geolocate the prefix. No lookup runs. |
| `no_match` | No suitable place evidence found. |
| `invalid_input` | The input wasn't valid for the service. |
| `backend_unavailable` | The service couldn't complete that row. May be retryable. |

Only `rowKey`, `countryCode`, `regionCode`, `cityName`, and `searchMode` cross the boundary. `rowKey` is an opaque, batch-unique correlation key, echoed unchanged. Prefixes, the feed, comments, Analysis JSON, RDAP data, publisher details, proposals, and approvals **do not**. Exact repeated place queries are sent once and safely fanned back to their rows. If MCP is unavailable, keep working with the offline report.

Review [Fastah's privacy policy](https://www.iubenda.com/privacy-policy/40053234) and [terms of use](https://mcp.fastah.ai/terms-of-use.txt) before enabling this step.

> **Running in a managed AI host?** The MCP endpoint is `mcp.fastah.ai`. If your org uses an egress allowlist, this host must be on it — otherwise the stage can't send anything, even with the plugin installed and signed in. The offline analysis is unaffected.

---

## Limits and troubleshooting

| Situation | What happens | First response |
|---|---|---|
| Python below 3.14, or a 3.14 release candidate | The CLI refuses to run. | Install Python **3.14 final** (see [Install](#install)). RCs are rejected on purpose. |
| Up to 400,000 data rows | The complete feed can be analyzed. Comments/blank lines don't count. | Keep the complete source; review output sizes. |
| More than 400,000 data rows | Analysis stops before any partial JSON. Nothing is truncated. | Don't split the feed to dodge the limit. Reduce scope through normal source management. |
| Invalid UTF-8 | Local analysis stops with an encoding error. | Keep the original; save a separate verified UTF-8 working copy. |
| Remote feed URL blocked | The download is the host's job; allowlisted networks may block it. | Use the host's normal download, or upload the CSV. Don't bypass policy or rebuild it. |
| GeoJSON without geometry | Features exist for every row, but geometry is null without MCP place evidence. | Use per-feature properties for tables; run optional MCP (after agreeing to its privacy boundary) to add geometry. RDAP doesn't add geometry. |
| Declared non-UTF-8 source | The analyzer won't silently convert it. | Keep the raw file; make a separate strict UTF-8 copy with both digests. |
| Prefix has host bits | The authored CIDR is kept but marked invalid. | Confirm the intended network address; don't accept auto-masking blindly. |
| Invalid country/region code | The row is kept with a finding. | Check the intended ISO codes. Empty or `ZZ` country means do-not-geolocate. |
| Output file already exists | The command refuses to overwrite it. | Choose a new name; keep the earlier artifact for comparison. |
| RDAP or MCP partly fails | Typed `unavailable` results sit beside successful ones. | Continue offline; retry the optional stage later. |
| RDAP finishes in ~0s on a big feed | Every query was blocked, not instant. | Check whether RIR egress is allowed on your host. |
| Large HTML report | Can take real time and memory to build/open. | Use Markdown + JSON first. 400,000 rows is a hard input ceiling, not a dashboard target. |

---

## Publish the checked feed

Fastah NetOps Tools doesn't publish for you. Use this with your normal change process:

1. Reanalyze the corrected full CSV. Resolve or accept every remaining finding through your own review.
2. Confirm the publication copy is UTF-8 CSV with the intended complete prefix set.
3. Put the file at a stable HTTPS URL. Serve the CSV body directly — no login page, no HTML wrapper. Use `text/csv` where supported. Set sensible cache headers for collectors.
4. Coordinate with your RIR/NIR/LIR — or your provider — for the relevant `inetnum` / `inet6num` objects. Under [RFC 9632](https://www.rfc-editor.org/rfc/rfc9632.html), prefer one `geofeed:` HTTPS reference where supported; otherwise use the exact case-sensitive `remarks: Geofeed https://...` form.
5. If you use the optional RFC 9632 RPKI signature, follow your RPKI process and update the signature when the file or signing cert changes. This tool doesn't sign the feed.
6. Fetch the published URL as a collector would. Confirm status, bytes, encoding, and access from outside your network.
7. Monitor the URL and registry reference. Keep the previous known-good file and rollback steps.

RFC 8805 consumers treat a feed as a hint and refresh on their own schedule. Publishing doesn't guarantee when — or whether — a provider picks up a change.

---

## Versions and help

- Skill and plugin: `0.3.3`
- Analyzer and Analysis schema: `0.5.0` / `0.5.0`
- MCP response contract: `1.0`

These move independently. Include them with the source digest when you report a problem.

- Website: [https://getfastah.com/](https://getfastah.com/)
- Support: [support@getfastah.com](mailto:support@getfastah.com)
- [Privacy policy](https://www.iubenda.com/privacy-policy/40053234)
- [Terms of use](https://mcp.fastah.ai/terms-of-use.txt)
- [Contributing](CONTRIBUTING.md)
- [Migration from `geofeed-tuner`](MIGRATION.md)
