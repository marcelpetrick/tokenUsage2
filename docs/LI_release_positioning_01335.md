# LinkedIn release positioning and expanded fact bank — v0.13.35

Historical 0.13.35 material: video durations and test counts below describe that
release. The shared media files now show 0.14.0; see the
[current palette announcement](../media/LI_release_post_0140.md) for updated copy.

This companion reviews the existing LinkedIn material without replacing it and
provides evidence, framing and reusable angles for the public v0.13.35 launch on
11 October 2026.

## Review of the existing material

[`LI_facts.md`](LI_facts.md) is accurate and usefully evergreen. Its strongest
points are the local-first privacy model, cross-tool normalization, durable
history and operational context. It works well as a reference sheet, but it does
not yet turn those facts into a single market position or rank them for a launch.

[`LI_quickpost.md`](../media/LI_quickpost.md) is correctly marked as an archived
September snapshot. Its personal voice and concrete model mix are engaging, but
the historical month, screenshot-specific cost discussion and omitted URL make
it the wrong primary copy for today's software release.

The launch content should therefore keep the factual discipline of the first
document and the conversational voice of the second, while leading with the
problem tokenUsage2 solves.

## Recommended frame

**Category:** local-first observability for coding agents.

**One-line position:** tokenUsage2 gives developers one operational view of how
Claude Code, Codex CLI and OpenCode consume tokens across accounts, models,
projects and backends—without shipping transcript data to another service.

**Problem statement:** once several coding agents, accounts and inference routes
run in parallel, individual logs and quota widgets stop answering basic
portfolio-level questions: what is active, what is expensive, how much work is
cache reuse, which project or model drives a spike, and whether a problem is
local or provider-wide.

**Do call it:** an observability dashboard, usage monitor, operating view or
local control plane for coding-agent consumption.

**Do not call it:** an agent evaluator, prompt monitor, task-success tracker,
invoice calculator or chain-of-thought inspector. It measures usage metadata and
process state, not work quality or private conversation content.

## Audience and message map

| Audience | Lead with | Proof point | Useful question |
|---|---|---|---|
| Agentic/AI engineers | One view across several coding agents | Claude Code, Codex CLI and OpenCode normalize into the same token model | How do you observe several agents at once? |
| Platform and DevEx teams | Local operational visibility without another SaaS collector | Automatic account discovery, archive, quotas and provider health | Which signal would help your developers most? |
| Hands-on software developers | A btop-style terminal interface | Live feed, keyboard exploration, periods, groupings and breakdowns | Which grouping would you inspect first? |
| FinOps/cost-conscious builders | Separate fresh work from cache traffic | Total and fresh five-minute rates, cache share and standard-rate estimates | Do you measure cache reuse or only total tokens? |
| Python/open-source engineers | Small dependency surface and reproducible quality gate | Python 3.14, standard-library runtime, GPLv3+, 384 tests and 99.00% coverage | What would you add next? |
| Local-model users | Hosted and local routes remain distinct | Ollama/LM Studio routes can be recognized as zero token-price while unknown hosted routes remain unpriced | How do you mix hosted and local inference? |

## Expanded, evidence-backed facts

### Product scope

- Three supported coding-agent sources: Claude Code, Codex CLI and OpenCode.
- Three time scales: daily, ISO-weekly and monthly.
- Four metrics: total tokens including cache, fresh input plus output, output
  only and a standard-rate cost estimate.
- Six breakdown dimensions: account, tool, backend, model, project and session.
- Twenty stable categorical colours before a grouping palette repeats.
- Separate trailing five-minute rates for total traffic including cache and for
  fresh input plus output, both explicitly expressed per minute.
- The cache row is cache reads divided by all prompt tokens. It describes reuse,
  not quality or provider health.
- Independent Claude and OpenAI health bubbles distinguish operational, partial,
  complete-outage and unknown states when the opt-in monitor is enabled.

These claims map directly to the [feature overview](../README.md#what-it-shows),
[keyboard controls](../README.md#keys) and current implementation constants in
[`aggregate.py`](../src/tokenusage2/aggregate.py) and
[`render.py`](../src/tokenusage2/render.py).

### Local-first operation

- Runtime dependencies: zero; the package uses Python 3.14's standard library.
- Tool directories are read-only. tokenUsage2 writes only its own SQLite archive,
  exports and private view-preference state.
- Prompt and response bodies are not stored. Retained metadata is limited to
  usage facts such as timestamps, models, routes, projects, sessions and token
  components.
- Provider-health requests are disabled by default, unauthenticated and limited
  to official Claude and OpenAI status endpoints.
- Saved view preferences use private XDG state and can be removed immediately
  with `Shift+R` without touching configuration or usage history.

The exact boundaries are documented under [Privacy](../README.md#privacy) and
[Configuration](../README.md#configuration-optional).

### Engineering proof

- The v0.13.35 gate passes 384 tests with 99.00% branch coverage.
- The shared local/CI/release pipeline verifies formatting, lint, ShellCheck,
  generated history, tests, a rendered demo, source and wheel builds, a clean
  wheel installation and the installed version.
- Current project size: 13,360 non-blank, non-comment lines across 64 files;
  tests contain 0.77 lines per product-code line.
- The current retained archive contains 113,430 normalized events. The latest
  source-corpus profile covered 2,135 logs and 3.18 GiB; an unchanged rescan took
  39 ms in that reference run.
- Public demo media comes from the production renderer with deterministic
  synthetic data and fictional, redacted identities.

See the generated [project counts](history/loc-current.md), the
[release changelog](../CHANGELOG.md#01335) and the public
[v0.13.35 release](https://github.com/marcelpetrick/tokenUsage2/releases/tag/v0.13.35).

## Claims that need their qualifier

- **Cost:** say “standard-rate estimate,” not bill or invoice. Unknown prices
  stay visibly unpriced, and mixed totals are lower bounds marked with `≥`.
- **Offline:** say “offline by default.” Provider-health checks are an explicit,
  optional network feature.
- **Read-only:** say “read-only toward agent-tool directories.” The application
  maintains its own archive, exports and preference file.
- **Monitoring:** say “usage observability.” The tool does not inspect prompt
  meaning, response quality, goals, decisions or task completion.
- **Cache:** say “cache reuse share,” not cache efficiency or health score.
- **Performance:** present measurements as one observed reference run, not a
  universal latency promise.

## Launch-message architecture

1. **Hook:** the observability gap created by several agents and backends.
2. **Category:** local-first, btop-style coding-agent observability.
3. **Demonstration:** native vertical product tour from the real renderer.
4. **Three outcomes:** understand consumption, investigate spikes and retain
   history after source cleanup.
5. **Trust:** no API keys, no transcript bodies, no runtime dependencies, tested
   wheel and explicit pricing caveats.
6. **Release link:** give interested readers a direct next step.
7. **Conversation:** ask what signal they currently lack, not merely whether
   they like the project.

## Media and publishing recommendation

Upload [`tokenUsage2-linkedin.mp4`](../media/tokenUsage2-linkedin.mp4) as native
video. It is a silent 38.6-second H.264 tour at 720 × 900 (4:5), the vertical
ratio LinkedIn lists as recommended for video ads and well within the organic
video requirements. Keep the post text self-contained because the visual is
silent, and review the generated thumbnail before publishing.

LinkedIn's current help supports native video, custom thumbnails and captions;
it accepts 10–60 fps, 256 × 144 through 4096 × 2304 and aspect ratios from
1:2.4 to 2.4:1. Its guidance also warns against placing essential information at
the frame edges. The existing 4:5 cards keep the terminal and cue inside broad
margins. Sources: [sharing video on LinkedIn](https://www.linkedin.com/help/linkedin/answer/a7486279),
[posting overview](https://www.linkedin.com/help/linkedin/answer/a518996/posting-and-sharing-content-overview?lang=en)
and LinkedIn's [organic-marketing guidance](https://www.linkedin.com/business/marketing/blog/linkedin-ads/organic-marketing-techniques-to-keep-your-brand-visible-in-difficult-times).

## Hashtag strategy

Hashtags should classify the post for the intended community; the hook and
technical substance must carry the post. LinkedIn's own guidance recommends
checking that a hashtag's community and content are relevant before using it.

**Recommended release set — broad enough for discovery, narrow enough for fit:**

`#AgenticEngineering #AIObservability #DeveloperTools #Python #OpenSource`

**Tool-specific alternative — use for a follow-up demo, not in addition to the
entire release set:**

`#ClaudeCode #Codex #OpenCode #TerminalUI #LocalFirst`

The primary set targets the people most likely to care about the category. The
product names already appear naturally in the post body, so repeating every name
as a hashtag is unnecessary. CamelCase improves scanability and accessibility.

## Additional follow-up angles

1. **Cache is not free work:** explain total versus fresh throughput and why a
   multi-million-token total rate can coexist with a much lower fresh rate.
2. **Local and hosted in one chart:** show how model routes remain separate and
   why unknown hosted prices are not silently treated as zero.
3. **What survives cleanup:** tell the archive story and why transcript cleanup
   otherwise erases longitudinal usage history.
4. **The six cuts of one bucket:** demonstrate account, tool, backend, model,
   project and session breakdowns from the same data.
5. **A status page is not a local diagnosis:** contrast provider incidents with
   local parser/discovery/archive issues.
6. **Building a dependency-free TUI:** discuss ANSI rendering, SQLite, `/proc`,
   deterministic frames and the 99% coverage gate.
7. **Privacy boundaries by construction:** explain what metadata is retained and
   what content is deliberately never stored.
8. **Why cost remains an estimate:** show `≥`, unpriced models and local routes
   rather than claiming invoice accuracy.
