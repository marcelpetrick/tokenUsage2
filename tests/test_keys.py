# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import date

from tokenusage2 import keys


def test_record_keys_are_spelled_as_the_archive_holds_them() -> None:
    assert keys.claude_key("msg_a", "req_1") == "claude:msg_a:req_1"
    assert keys.opencode_key("opencode:x", "r1") == "opencode:opencode:x:r1"
    retained = keys.backfill_key("claude:~/.claude", date(2026, 9, 1), "claude-opus-5")
    assert retained == "claude-daily:claude:~/.claude:2026-09-01:claude-opus-5"
    assert retained.startswith(keys.backfill_prefix("claude:~/.claude"))


def test_account_key_prefixes_cover_every_key_that_carries_the_account() -> None:
    carrying = (keys.opencode_key("acct", "r1"), keys.backfill_key("acct", date(2026, 9, 1), "m"))
    assert [
        key.startswith(f"{prefix}acct:")
        for key, prefix in zip(carrying, keys.ACCOUNT_KEY_PREFIXES, strict=True)
    ] == [True, True]
    assert not keys.codex_key("t", 5).startswith(keys.ACCOUNT_KEY_PREFIXES)
    assert not keys.claude_key("m", "r").startswith(keys.ACCOUNT_KEY_PREFIXES)


def test_codex_keys_carry_their_compaction_restarts() -> None:
    assert [keys.codex_key("t", 5), keys.codex_key("t", 5, 12)] == ["codex:t:5", "codex:t:5:r12"]
    samples = ("codex:t:5:r12", "codex:t:5", "claude:m:req_1", "codex:t:5:rx", "")
    assert [keys.codex_restarts(key) for key in samples] == [12, 0, 0, 0, 0]


def test_meta_keys_and_the_scale_value_round_trip() -> None:
    assert keys.account_meta_keys("a") == (
        "statscache:a",
        "statscache-scale:a",
        "opencode-watermark:a",
    )
    assert keys.format_scale(0.5097962884, 26) == "0.509796:26"
    assert keys.parse_scale(keys.format_scale(0.5, 3)) == (0.5, 3)
    assert [keys.parse_scale(value) for value in (None, "", "abc", "0.5", "0.5:x")] == [None] * 5


def test_stats_cache_signatures_record_their_rule_version() -> None:
    signature = keys.stats_cache_signature(4, 29296, 17, date(2026, 8, 3), None)
    assert signature == "v4:29296:17:2026-08-03:None"
    samples = (signature, "29296:17:2026-08-03:None", None, "", "vx:1", "v12:1")
    assert [keys.signature_rule(value) for value in samples] == [4, 0, 0, 0, 0, 12]
