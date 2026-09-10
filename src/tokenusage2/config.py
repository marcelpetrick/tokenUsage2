# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Optional user configuration, read from ``$XDG_CONFIG_HOME/tokenusage2/config.toml``.

Everything here is optional: discovery works without a file. The file only
adds homes that cannot be found automatically, hides homes, renames accounts
and pins models to backend labels.
"""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tokenusage2.pricing import Rates

_VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


class ConfigError(ValueError):
    """The configuration file exists but cannot be used."""


@dataclass(frozen=True, slots=True)
class AlertSettings:
    """When to raise an alert, and how."""

    quota_percent: float = 90.0
    burn_factor: float = 5.0
    burn_floor: float = 250_000.0
    notify: bool = False
    bell: bool = False


@dataclass(frozen=True, slots=True)
class Config:
    claude_homes: tuple[Path, ...] = ()
    codex_homes: tuple[Path, ...] = ()
    opencode_dbs: tuple[Path, ...] = ()
    ignore: tuple[Path, ...] = ()
    scan_home: bool = True
    rc_files: tuple[Path, ...] | None = None
    labels: Mapping[str, str] = field(default_factory=dict)
    backends: Mapping[str, str] = field(default_factory=dict)
    prices: tuple[tuple[str, Rates], ...] = ()
    alerts: AlertSettings = field(default_factory=AlertSettings)
    source: Path | None = None


def expand(raw: str, home: Path, env: Mapping[str, str]) -> Path:
    """Expand ``~`` and ``$VARS`` against the given home and environment."""
    value = raw.strip()
    if value == "~" or value.startswith("~/"):
        value = str(home) + value[1:]
    scope = {**env, "HOME": str(home)}
    value = _VARIABLE.sub(lambda match: scope.get(match.group(1), match.group(0)), value)
    return Path(value)


def default_config_path(home: Path, env: Mapping[str, str]) -> Path:
    base = env.get("XDG_CONFIG_HOME") or str(home / ".config")
    return Path(base) / "tokenusage2" / "config.toml"


def _paths(table: Mapping[str, object], key: str, home: Path, env: Mapping[str, str]) -> tuple:
    raw = table.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigError(f"discovery.{key} must be a list of paths")
    return tuple(expand(item, home, env) for item in raw)


def _strings(data: Mapping[str, object], key: str) -> dict[str, str]:
    raw = data.get(key, {})
    if not isinstance(raw, dict) or not all(isinstance(v, str) for v in raw.values()):
        raise ConfigError(f"[{key}] must map strings to strings")
    return dict(raw)


_PRICE_FIELDS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")


def _alerts(data: Mapping[str, object]) -> AlertSettings:
    """``[alerts]``: quota_percent, burn_factor, burn_floor, notify, bell."""
    raw = data.get("alerts", {})
    if not isinstance(raw, dict):
        raise ConfigError("[alerts] must be a table")
    known = {"quota_percent", "burn_factor", "burn_floor", "notify", "bell"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigError(f"[alerts]: unknown keys {', '.join(unknown)}")
    values: dict[str, object] = {}
    for name in ("notify", "bell"):
        if name in raw:
            if not isinstance(raw[name], bool):
                raise ConfigError(f"alerts.{name} must be true or false")
            values[name] = raw[name]
    limits = {"quota_percent": (0.0, 100.0), "burn_factor": (0.0, None), "burn_floor": (0.0, None)}
    for name, (low, high) in limits.items():
        if name not in raw:
            continue
        value = raw[name]
        valid = not isinstance(value, bool) and isinstance(value, int | float)
        if not valid or value < low or (high is not None and value > high):
            bound = f"between {low:g} and {high:g}" if high is not None else f">= {low:g}"
            raise ConfigError(f"alerts.{name} must be a number {bound}")
        values[name] = float(value)
    return AlertSettings(**values)


def _prices(data: Mapping[str, object]) -> tuple[tuple[str, Rates], ...]:
    """``[prices."<model glob>"]`` tables in USD per 1M tokens, in file order."""
    raw = data.get("prices", {})
    if not isinstance(raw, dict):
        raise ConfigError("[prices] must be a table of model globs")
    found = []
    for pattern, entry in raw.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"prices.{pattern!r} must be a table")
        unknown = sorted(set(entry) - set(_PRICE_FIELDS))
        if unknown:
            raise ConfigError(f"prices.{pattern!r}: unknown keys {', '.join(unknown)}")
        values = {}
        for name, value in entry.items():
            if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
                raise ConfigError(f"prices.{pattern!r}.{name} must be a number >= 0")
            values[name] = float(value)
        if "input" not in values or "output" not in values:
            raise ConfigError(f"prices.{pattern!r} needs at least input and output")
        write = values.get("cache_write", values["input"])
        found.append(
            (
                pattern,
                Rates(
                    values["input"],
                    values["output"],
                    values.get("cache_read", values["input"]),
                    write,
                    values.get("cache_write_1h", write),
                ),
            )
        )
    return tuple(found)


def load_config(path: Path | None, home: Path, env: Mapping[str, str]) -> Config:
    """Load ``path`` (or the default location). A missing file is an empty config."""
    target = path or default_config_path(home, env)
    if not target.is_file():
        if path is not None:
            raise ConfigError(f"config file not found: {path}")
        return Config()
    try:
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"{target}: {error}") from error
    discovery = data.get("discovery", {})
    if not isinstance(discovery, dict):
        raise ConfigError("[discovery] must be a table")
    scan_home = discovery.get("scan_home", True)
    if not isinstance(scan_home, bool):
        raise ConfigError("discovery.scan_home must be true or false")
    rc_files = _paths(discovery, "rc_files", home, env) if "rc_files" in discovery else None
    labels = {str(expand(k, home, env)): v for k, v in _strings(data, "labels").items()}
    return Config(
        claude_homes=_paths(discovery, "claude_homes", home, env),
        codex_homes=_paths(discovery, "codex_homes", home, env),
        opencode_dbs=_paths(discovery, "opencode_dbs", home, env),
        ignore=_paths(discovery, "ignore", home, env),
        scan_home=scan_home,
        rc_files=rc_files,
        labels=labels,
        backends=_strings(data, "backends"),
        prices=_prices(data),
        alerts=_alerts(data),
        source=target,
    )
