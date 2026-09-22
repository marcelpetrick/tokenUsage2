#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Direct and render three privacy-safe tokenUsage2 product tours.

Every dashboard frame comes from the real renderer and deterministic demo data.
Chromium turns the ANSI output into a 4:5 social-media card; ImageMagick and
FFmpeg assemble the cards into GIF and MP4 versions.
"""

import html
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tokenusage2.demo import ACCOUNTS, DemoSource  # noqa: E402
from tokenusage2.model import Account  # noqa: E402
from tokenusage2.render import View, render  # noqa: E402
from tokenusage2.tui import Controller, bucket_count, data_span, take_snapshot  # noqa: E402

OUTPUT_DIR = ROOT / "media"
WIDTH, HEIGHT = 720, 900
COLUMNS, ROWS = 120, 40
NOW = datetime(2026, 9, 22, 14, 24, tzinfo=ZoneInfo("Europe/Berlin")).timestamp()
SGR = re.compile(r"\x1b\[([0-9;]*)m")
BASE16 = (
    "#000000",
    "#cd0000",
    "#00cd00",
    "#cdcd00",
    "#0000ee",
    "#cd00cd",
    "#00cdcd",
    "#e5e5e5",
    "#7f7f7f",
    "#ff0000",
    "#00ff00",
    "#ffff00",
    "#5c5cff",
    "#ff00ff",
    "#00ffff",
    "#ffffff",
)
PUBLIC_ACCOUNTS = tuple(
    replace(account, label=label, identity=identity)
    for account, label, identity in zip(
        ACCOUNTS,
        ("atlas", "ember", "lumen", "nova"),
        (
            "ada@northstar.invalid",
            "lin@paperkite.invalid",
            "sam@moonbase.invalid",
            None,
        ),
        strict=True,
    )
)
PUBLIC_PROJECTS = {
    "tokenUsage2": "northstar",
    "AgentWhileTrue": "paperkite",
    "Cullendula": "moonbase",
    "abtop": "harbor",
    "grocery-list": "garden",
    "dotfiles": "workbench",
}


@dataclass(frozen=True, slots=True)
class Scene:
    key: str | None
    heading: str
    caption: str
    duration: float = 1.4


@dataclass(frozen=True, slots=True)
class Story:
    slug: str
    title: str
    kicker: str
    scenes: tuple[Scene, ...]


STORIES = (
    Story(
        "tour",
        "One dashboard. Every time scale.",
        "PERIODS · METRICS · THEMES",
        (
            Scene(None, "Start with today", "Live totals, quotas, timeline and request feed."),
            Scene("w", "Zoom out to weeks", "One key changes the complete aggregation."),
            Scene("m", "Monthly history", "The monthly view reaches across the full history."),
            Scene("d", "Back to daily", "Return to the most actionable operating view."),
            Scene("v", "Fresh tokens", "Separate new input and output from cache traffic."),
            Scene("v", "Output only", "Focus on generated output across every tool."),
            Scene("v", "Cost estimate", "Compare standard-rate estimates in the same view."),
            Scene("t", "Midnight theme", "Change the palette without leaving the dashboard."),
            Scene("t", "Amber theme", "A warmer high-contrast terminal palette.", 2.0),
        ),
    ),
    Story(
        "groupings",
        "Ask the same data new questions.",
        "GROUPING · BREAKDOWN · FILTERS",
        (
            Scene(None, "Colour by account", "See which fictional account drives each bucket."),
            Scene("g", "Colour by tool", "Compare Claude Code, Codex CLI and OpenCode."),
            Scene("g", "Colour by backend", "Separate hosted and local inference routes."),
            Scene("g", "Colour by model", "Reveal the model mix behind each time bucket."),
            Scene("g", "Colour by project", "Follow activity across synthetic projects."),
            Scene("b", "Break down by project", "Re-cut the selected bucket without rescanning."),
            Scene("b", "Break down by session", "Inspect individual synthetic work sessions."),
            Scene("a", "Filter one account", "Focus the whole dashboard on Atlas.", 2.0),
        ),
    ),
    Story(
        "explore",
        "From overview to investigation.",
        "HEATMAP · HISTORY · HELP · COLOUR",
        (
            Scene(
                None,
                "Live request feed",
                "Recent synthetic requests update beside the breakdown.",
            ),
            Scene("h", "Open the heatmap", "Spot recurring activity by weekday and hour."),
            Scene("h", "Return to the feed", "One key flips the investigative panel."),
            Scene("left", "Inspect yesterday", "Move the cursor back through historical buckets."),
            Scene("left", "Keep travelling", "The breakdown follows the selected day."),
            Scene("?", "Show keyboard help", "Every interaction stays discoverable.", 1.8),
            Scene("esc", "Close and continue", "Escape returns to the live dashboard."),
            Scene("t", "Switch to midnight", "Themes change instantly while redaction stays on."),
            Scene("t", "Finish in amber", "A final high-contrast view for the feed.", 2.0),
        ),
    ),
)


class PublicDemo(DemoSource):
    """Demo source with explicitly fictional public-facing account metadata."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._events = [
            replace(
                event,
                project=f"/demo/{PUBLIC_PROJECTS[project]}",
                session=f"session-{PUBLIC_PROJECTS[project]}",
            )
            if (project := Path(event.project).name) in PUBLIC_PROJECTS
            else event
            for event in self._events
        ]

    def accounts(self) -> list[Account]:
        return list(PUBLIC_ACCOUNTS)


def xterm(index: int) -> str:
    if index < 16:
        return BASE16[index]
    if index < 232:
        index -= 16
        steps = (0, 95, 135, 175, 215, 255)
        red, green, blue = steps[index // 36], steps[index // 6 % 6], steps[index % 6]
        return f"#{red:02x}{green:02x}{blue:02x}"
    grey = 8 + (index - 232) * 10
    return f"#{grey:02x}{grey:02x}{grey:02x}"


def to_html(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        position = 0
        for match in SGR.finditer(line):
            if chunk := line[position : match.start()]:
                out.append(html.escape(chunk))
            codes = [int(code) for code in match.group(1).split(";") if code] or [0]
            out.append("</span>")
            foreground = background = None
            bold = False
            index = 0
            while index < len(codes):
                code = codes[index]
                if code == 1:
                    bold = True
                elif code in {38, 48} and index + 2 < len(codes) and codes[index + 1] == 5:
                    if code == 38:
                        foreground = xterm(codes[index + 2])
                    else:
                        background = xterm(codes[index + 2])
                    index += 2
                index += 1
            styles = ";".join(
                part
                for part in (
                    f"color:{foreground}" if foreground else "",
                    f"background:{background}" if background else "",
                    "font-weight:700" if bold else "",
                )
                if part
            )
            out.append(f'<span style="{styles}">')
            position = match.end()
        out.append(html.escape(line[position:]))
        out.append("</span>\n<span>")
    return "".join(out)


def dashboard(source: PublicDemo, view: View) -> str:
    count = bucket_count(
        view,
        COLUMNS,
        ROWS,
        len(source.accounts()),
        data_span(source, view, NOW, source.tz),
    )
    snapshot = take_snapshot(source, view, now=NOW, tz=source.tz, count=count)
    lines = render(
        snapshot,
        view,
        COLUMNS,
        ROWS,
        tz=source.tz,
        status="synthetic demo · no files read · identities redacted",
        mode="DEMO",
    )
    text = "\n".join(lines)
    private_markers = (
        "ada@northstar.invalid",
        "lin@paperkite.invalid",
        "sam@moonbase.invalid",
        "AgentWhileTrue",
        "Cullendula",
        "abtop",
        "grocery-list",
        "dotfiles",
    )
    for marker in private_markers:
        if marker in text:
            raise RuntimeError(f"private marker in rendered frame: {marker}")
    return text


def page(story: Story, scene: Scene, frame: str) -> str:
    key = "READY" if scene.key is None else scene.key.upper()
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}} html,body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;overflow:hidden}}
body{{background:radial-gradient(circle at 20% 0%,#203046 0,#111827 38%,#090d14 100%);
color:#f8fafc;font-family:Inter,'Noto Sans',sans-serif;padding:32px 18px 28px}}
.kicker{{font-size:12px;font-weight:800;letter-spacing:2.4px;color:#67e8f9;margin:0 0 8px}}
h1{{font-size:30px;line-height:1.06;letter-spacing:-.6px;margin:0 0 24px}}
.terminal{{background:#1c1c1c;border:1px solid #334155;border-radius:12px;padding:10px 8px;
box-shadow:0 18px 50px #0009;overflow:hidden;height:540px}}
pre{{margin:0;font:9px/13px 'DejaVu Sans Mono','Noto Sans Mono',monospace;white-space:pre}}
.cue{{display:grid;grid-template-columns:74px 1fr;gap:14px;align-items:center;margin:24px 8px 0}}
.key{{height:58px;border-radius:12px;background:#f8fafc;color:#111827;display:flex;
align-items:center;justify-content:center;font:800 13px/1 'DejaVu Sans Mono',monospace;
box-shadow:0 5px 0 #94a3b8;overflow-wrap:anywhere;text-align:center;padding:5px}}
h2{{font-size:22px;line-height:1.1;margin:0 0 6px}} .caption{{color:#cbd5e1;font-size:15px;
line-height:1.3;margin:0}} .footer{{position:absolute;left:26px;right:26px;bottom:14px;
display:flex;justify-content:space-between;color:#64748b;font-size:11px;font-weight:700;
letter-spacing:.6px}}
</style></head><body>
<p class="kicker">{html.escape(story.kicker)}</p><h1>{html.escape(story.title)}</h1>
<div class="terminal"><pre><span>{to_html(frame)}</span></pre></div>
<div class="cue"><div class="key">{html.escape(key)}</div><div><h2>{html.escape(scene.heading)}</h2>
<p class="caption">{html.escape(scene.caption)}</p></div></div>
<div class="footer"><span>tokenUsage2</span><span>100% SYNTHETIC · REDACTION ON</span></div>
</body></html>"""


def screenshot(browser: str, document: Path, output: Path) -> None:
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--log-level=3",
            f"--window-size={WIDTH},{HEIGHT}",
            f"--screenshot={output}",
            document.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def make_gif(magick: str, frames: list[tuple[Path, float]], output: Path) -> None:
    command = [magick]
    for frame, duration in frames:
        command.extend(("-delay", str(round(duration * 100)), str(frame)))
    command.extend(("-loop", "0", "-layers", "Optimize", "-colors", "96", str(output)))
    subprocess.run(command, check=True)


def make_mp4(ffmpeg: str, frames: list[tuple[Path, float]], output: Path, scratch: Path) -> None:
    manifest = scratch / "frames.ffconcat"
    lines = ["ffconcat version 1.0"]
    for frame, duration in frames:
        lines.extend((f"file '{frame}'", f"duration {duration}"))
    lines.append(f"file '{frames[-1][0]}'")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(
        [
            ffmpeg,
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-t",
            str(sum(duration for _, duration in frames)),
            "-vf",
            "fps=15,format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "21",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def make_combined_mp4(ffmpeg: str, inputs: list[Path], output: Path, scratch: Path) -> None:
    manifest = scratch / "combined.ffconcat"
    lines = ["ffconcat version 1.0", *(f"file '{path}'" for path in inputs)]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(
        [
            ffmpeg,
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def render_story(browser: str, magick: str, ffmpeg: str, story: Story, scratch: Path) -> None:
    source = PublicDemo(ZoneInfo("Europe/Berlin"), clock=lambda: NOW)
    view = View(theme="default", redact=True)
    controller = Controller(view)
    account_ids = [account.id for account in source.accounts()]
    frames: list[tuple[Path, float]] = []
    for index, scene in enumerate(story.scenes):
        if scene.key is not None:
            controller.handle(scene.key, account_ids)
        if not view.redact:
            raise RuntimeError("a storyboard disabled identity redaction")
        frame = dashboard(source, view)
        document = scratch / f"{story.slug}-{index:02}.html"
        image = scratch / f"{story.slug}-{index:02}.png"
        document.write_text(page(story, scene, frame), encoding="utf-8")
        screenshot(browser, document, image)
        frames.append((image, scene.duration))
    make_gif(magick, frames, OUTPUT_DIR / f"tokenUsage2-{story.slug}.gif")
    make_mp4(ffmpeg, frames, OUTPUT_DIR / f"tokenUsage2-{story.slug}.mp4", scratch)


def main() -> int:
    browser = shutil.which("chromium") or shutil.which("google-chrome")
    magick = shutil.which("magick")
    ffmpeg = shutil.which("ffmpeg")
    tools = (("Chromium", browser), ("ImageMagick", magick), ("FFmpeg", ffmpeg))
    missing = [name for name, path in tools if not path]
    if missing:
        print(f"record_gifs.py needs {', '.join(missing)} on PATH", file=sys.stderr)
        return 1
    OUTPUT_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tokenusage2-gifs-") as directory:
        scratch = Path(directory)
        for story in STORIES:
            render_story(browser, magick, ffmpeg, story, scratch)
        make_combined_mp4(
            ffmpeg,
            [OUTPUT_DIR / f"tokenUsage2-{story.slug}.mp4" for story in STORIES],
            OUTPUT_DIR / "tokenUsage2-linkedin.mp4",
            scratch,
        )
    for story in STORIES:
        for suffix in ("gif", "mp4"):
            output = OUTPUT_DIR / f"tokenUsage2-{story.slug}.{suffix}"
            print(f"wrote {output.relative_to(ROOT)} ({output.stat().st_size / 1_000_000:.2f} MB)")
    combined = OUTPUT_DIR / "tokenUsage2-linkedin.mp4"
    print(f"wrote {combined.relative_to(ROOT)} ({combined.stat().st_size / 1_000_000:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
