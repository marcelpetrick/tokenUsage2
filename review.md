Base: origin/master @ 3c20118   Head: ff6231d
Files changed: 8   +99 / -32 lines

## Findings

No Code or Architecture findings. The executable changes update the exact
development-only Ruff pin from the latest previous patch to the current stable,
non-yanked patch and direct the deterministic screenshot generator to the image
used by the README. The remaining changes synchronize documentation and record
the earlier dependency review. The full lint, format, test, coverage, smoke,
build, clean-wheel and version gates pass with the resolved dependency set.

## Verdict

The branch is mergeable as reviewed. There are no HIGH or MEDIUM findings to
fix.
