<!--
SPDX-FileCopyrightText: 2026 Marcel Petrick

SPDX-License-Identifier: GPL-3.0-or-later
-->

# tokenUsage2 0.14.0 — press p, find your colours

Release announcement copy for the palette feature. The refreshed
[tokenUsage2 tour](tokenUsage2-tour.mp4) shows three consecutive palette changes;
the [combined tour](tokenUsage2-linkedin.mp4) also covers grouping and exploration.

Published on 23 October 2026 as a public stable
[GitHub release](https://github.com/marcelpetrick/tokenUsage2/releases/tag/v0.14.0).
The tour is 17.4 seconds; the combined cut is 42.8 seconds. Both use H.264 at
720 × 900. [Release verification](../review.md) records the CI and artifact evidence.

## Suggested post

```text
Small feature, immediate payoff: press p, find your colours.

tokenUsage2 0.14.0 lets you explore shuffled category palettes while the dashboard is running. Keep pressing p until the chart looks right to you. Your choice is remembered for the next launch.

The timeline, legend and matching breakdown stay in sync, with 20 distinct category colours before repetition.

p → try another category palette
t → switch the overall theme
Space → pause or resume live refresh
Shift+R → restore the factory view

If you have not tried tokenUsage2 yet: it is a local-first terminal dashboard for Claude Code, Codex CLI and OpenCode usage across accounts, models, backends, projects and sessions. Python 3.14, zero third-party runtime dependencies, no API keys, and no stored prompts or responses.

This release also updates the pinned build and lint tools. The full release gate passes 400 tests with 99.00% branch coverage.

The tour uses the real renderer with deterministic synthetic data and fictional, redacted identities.

Release and downloads:
https://github.com/marcelpetrick/tokenUsage2/releases/tag/v0.14.0

#DeveloperTools #TerminalUI #Python #OpenSource #LocalFirst
```

## Short version

```text
tokenUsage2 0.14.0 is out: press p to explore category palettes without restarting. Keep a combination you like; it returns next launch.

t still changes the overall theme. Space now pauses/resumes refresh.

Local-first usage observability for Claude Code, Codex CLI and OpenCode. Zero third-party runtime dependencies.

https://github.com/marcelpetrick/tokenUsage2/releases/tag/v0.14.0

#DeveloperTools #TerminalUI #Python #OpenSource
```

## Demonstration notes

- Attach the refreshed tour MP4 or GIF; it shows actual `p` key handling and
  rendering, with three consecutive category palette changes.
- Use the default, midnight or amber theme; plain intentionally has no colours.
- Palette exploration rearranges existing category colours. It does not change
  token accounting, archived history or provider-status meanings.
- Copy is prepared for sharing; no social post is published by the release.
