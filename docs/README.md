<!--
SPDX-FileCopyrightText: 2026 Marcel Petrick

SPDX-License-Identifier: GPL-3.0-or-later
-->

# tokenUsage2 documentation

Current stable release: [v0.14.0 — press p, find your colours](https://github.com/marcelpetrick/tokenUsage2/releases/tag/v0.14.0),
published on 23 October 2026. It includes saved category palettes and the pinned
setuptools 84.2.1 / Ruff 0.17.2 updates. Runtime dependencies remain empty.

## Current guidance

| Document | Purpose |
|---|---|
| [README](../README.md) | Install, upgrade, keyboard controls, sources, accounting, privacy and development |
| [Plan and architecture](../PLAN.md) | Implemented features, module responsibilities, historical work and release evidence |
| [Changelog](../CHANGELOG.md) | Versioned changes and unreleased documentation corrections |
| [Documentation review](../review.md) | Current documentation audit and verified public-release evidence |
| [Contributor guidance](../AGENTS.md) | Product invariants, atomic commits and validation rules |
| [Publication facts](LI_facts.md) | Current product claims and qualifications |
| [0.14.0 announcement](../media/LI_release_post_0140.md) | Ready-to-share palette release copy and demo links |
| [Generated project counts](history/loc-current.md) | Counts at the current documentation commit; generated with the history chart |

## Palette controls

- `p`: try another shuffled arrangement of the 20 category colours. Timeline,
  legend and matching breakdown stay aligned; the choice survives restarts.
- `t`: cycle default, midnight, amber and plain themes. Plain stays uncoloured.
- `Space`: pause or resume live refresh, including while exploring palettes.
- `Shift+R`: restore factory view settings and forget saved preferences.

Palette selection is interactive. Non-interactive outputs keep factory defaults
unless supported CLI flags override them; there is no `--palette` option.
Preferences live in `$XDG_STATE_HOME/tokenusage2/view.json`. Reset removes only
that state, leaving configuration, source data and the usage archive intact.

## Demonstrations

The [tour GIF](../media/tokenUsage2-tour.gif) and
[tour MP4](../media/tokenUsage2-tour.mp4) show three successive `p` presses.
The [combined MP4](../media/tokenUsage2-linkedin.mp4) runs for 42.8 seconds.
Generated tours use deterministic synthetic data, fictional identities and the
production renderer. Regenerate them with
`.venv/bin/python scripts/record_gifs.py` from the repository root.

The README's separately captioned v0.13.33 live screenshot is historical media.
Performance figures dated 11 October 2026 describe that reference corpus and run;
they have not been remeasured for the palette release.

## Historical material

These documents preserve their original release claims and measurements; their
introductory notes point to current material. Shared tour filenames now contain
the regenerated 0.14.0 demonstrations.

| Document | Historical scope |
|---|---|
| [0.13.35 positioning](LI_release_positioning_01335.md) | October 2026 launch framing and publishing sources |
| [0.13.35 findings](LI_review_findings_01335.md) | Claim review for that release |
| [0.13.35 announcement](../media/LI_release_post_01335.md) | Earlier launch copy, test counts and video duration |
| [September quick post](../media/LI_quickpost.md) | Snapshot-specific model-usage discussion |
