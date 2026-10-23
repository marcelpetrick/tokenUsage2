# LinkedIn review findings — tokenUsage2 v0.13.35

Historical 0.13.35 material: video durations and test counts below describe that
release. The shared media files now show 0.14.0; see the
[current palette announcement](../media/LI_release_post_0140.md) for updated copy.

**Review date:** 11 October 2026

**Purpose:** preserve the findings behind the release positioning and launch
copy as a separate, auditable record.

## Scope reviewed

- Existing source material: [`LI_facts.md`](LI_facts.md) and
  [`LI_quickpost.md`](../media/LI_quickpost.md).
- Current product documentation, changelog, configuration, renderer, provider
  status implementation and their tests.
- The release video at [`tokenUsage2-linkedin.mp4`](../media/tokenUsage2-linkedin.mp4).
- LinkedIn's official posting, native-video and organic-content guidance.

The existing source documents were treated as read-only. New positioning and
publishable copy live in
[`LI_release_positioning_01335.md`](LI_release_positioning_01335.md) and
[`LI_release_post_01335.md`](../media/LI_release_post_01335.md).

## Findings

### 1. The strongest category is coding-agent usage observability

“Agentic monitoring” is too broad on its own: it can imply evaluation of an
agent's reasoning, decisions, output quality or task completion. tokenUsage2
observes operational usage metadata instead. The accurate frame is therefore
**local-first observability for coding agents**, optionally described as a
“btop-style usage dashboard.”

Publication implication: pair “agentic” with “usage,” “operational” or
“observability”; do not claim semantic agent monitoring.

### 2. The cross-tool view is the clearest differentiator

The product normalizes Claude Code, Codex CLI and OpenCode data into one view
across accounts, backends, models, projects and sessions. This answers a more
specific problem than generic token counting: individual agent logs and quota
views do not provide one portfolio-level operating picture.

Publication implication: lead with the fragmented multi-agent problem before
listing implementation details.

### 3. Total rate and fresh rate tell different stories

The total five-minute rate includes cache traffic. It can legitimately reach
millions of tokens per minute when several agents perform cache-heavy work. The
fresh rate counts fresh input plus output and better represents newly processed
traffic. Both are trailing five-minute averages expressed per minute—not totals
over five minutes.

Publication implication: use this contrast as a concrete demonstration of why
the dashboard is useful. Never present total rate alone as “new work.”

### 4. Cache share is descriptive, not a score

The timeline's `cache%` value is cache reads divided by prompt tokens: fresh
input plus cache reads plus cache writes. Its neutral placement below the bars
expresses reuse for the same time bucket. It is neither provider health nor a
universal efficiency score; high or low can be appropriate for different work.

Publication implication: say “cache-reuse share,” not “cache health” or “cache
quality.”

### 5. The privacy story is strong but needs exact boundaries

The program reads agent-tool directories without modifying them, retains usage
metadata in its own SQLite archive and does not retain prompt or response
bodies. It does write its own archive, exports and view preferences. Network
access remains off by default; provider-status checks are an explicit opt-in.

Publication implication: say “read-only toward agent-tool directories” and
“offline by default,” rather than the unqualified “read-only” or “offline.”

### 6. Provider health is operational context, not local diagnosis

Separate Claude and OpenAI badges report operational, degraded/maintenance,
outage or unknown states from official provider status APIs. Tests cover the
mapping, timeouts, failures and rendered badge states. A green provider badge
does not prove that local discovery, parsing, credentials or networking works.

Publication implication: present the badges as a way to distinguish known
provider incidents from likely local investigation—not as an end-to-end API
probe.

### 7. Cost is intentionally an estimate

Cost uses standard-rate model pricing. Unknown hosted prices remain unpriced,
mixed incomplete totals are marked as lower bounds, and recognized local routes
can be zero-priced. That behavior is more trustworthy than silently treating
unknown hosted models as free, but it cannot reproduce an invoice.

Publication implication: consistently use “standard-rate cost estimate.”

### 8. Engineering evidence supports a technical audience

The release has no third-party runtime dependencies, targets Python 3.14 and is
GPLv3+. Its release gate reports 384 tests and 99.00% branch coverage. The
measured reference corpus covers 2,135 logs, 3.18 GiB and 113,430 retained
events; the 39 ms unchanged rescan is a measured reference run, not a universal
latency guarantee.

Publication implication: use these facts as trust evidence after explaining
the user problem. Qualify benchmark figures as measurements.

### 9. The existing video fits a native LinkedIn post

The 38.6-second H.264 video is 720 × 900 (4:5), which is within LinkedIn's
documented native-video dimensions and aspect-ratio range. It is silent, so the
post must remain understandable without audio and the thumbnail should make
the product recognizable. The footage comes from the production renderer with
deterministic synthetic data and fictional identities.

Publication implication: upload the file natively, keep the accompanying text
self-contained and check the thumbnail and edge-safe content before publishing.

### 10. Hashtags should classify the post, not carry it

No defensible evidence guarantees that a particular hashtag set maximizes
reach. Relevance to the intended audience is the useful selection criterion.
The release set balances category, problem space, builder audience,
implementation ecosystem and distribution model:

`#AgenticEngineering #AIObservability #DeveloperTools #Python #OpenSource`

Tool-name hashtags are better reserved for a focused follow-up post because the
three product names already appear in the launch copy. CamelCase makes compound
hashtags easier to scan.

## Claim ledger

| Claim | Status | Evidence or necessary qualifier |
|---|---|---|
| Three supported agent sources | Verified | README feature and source tables |
| Three periods, four metrics, six dimensions | Verified | README controls and aggregation/rendering implementation |
| Twenty category colours before repetition | Verified | Renderer palette and changelog |
| Total and fresh rates are per minute | Verified | Five-minute rate rendering and tests |
| Separate Claude/OpenAI status bubbles | Verified | Provider-status implementation and renderer tests |
| Provider badges prove API access works | Rejected | They summarize public status components, not the user's authenticated request path |
| No prompt or response bodies retained | Verified | Privacy documentation and ingestion/archive model |
| Completely offline | Needs qualifier | True by default; optional provider-status checks use the network |
| Exact billing cost | Rejected | Standard-rate estimate with explicit unknown/lower-bound handling |
| 39 ms rescans for every user | Rejected | One measured unchanged-rescan reference run |
| “Maximum reach” hashtag set | Not provable | Use audience relevance rather than a reach guarantee |

## Source trail

Repository evidence:

- [README feature overview](../README.md#what-it-shows)
- [README privacy boundaries](../README.md#privacy)
- [README configuration](../README.md#configuration-optional)
- [Changelog for v0.13.35](../CHANGELOG.md#01335)
- [`provider_status.py`](../src/tokenusage2/provider_status.py)
- [`test_provider_status.py`](../tests/test_provider_status.py)
- [`render.py`](../src/tokenusage2/render.py)
- [`test_render.py`](../tests/test_render.py)

External publishing evidence:

- LinkedIn Help: [Posting and sharing content overview](https://www.linkedin.com/help/linkedin/answer/a518996/posting-and-sharing-content-overview?lang=en)
- LinkedIn Help: [Share videos on LinkedIn](https://www.linkedin.com/help/linkedin/answer/a7486279)
- LinkedIn Marketing: [Organic marketing guidance](https://www.linkedin.com/business/marketing/blog/linkedin-ads/organic-marketing-techniques-to-keep-your-brand-visible-in-difficult-times)

## Decision

Use the recommended launch post and native video for the release. Frame the
software as a local-first operational view across coding agents, foreground the
total-versus-fresh distinction, and retain the qualifications above wherever a
shorter version is derived. The positioning is specific enough to be credible
while still addressing agentic-engineering, DevEx, observability and open-source
audiences.
