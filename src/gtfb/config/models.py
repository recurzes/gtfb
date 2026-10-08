"""Domain models for GTFB configuration."""

from dataclasses import asdict, dataclass, field
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TRUE_STRINGS = {"true", "1", "yes", "on"}
_FALSE_STRINGS = {"false", "0", "no", "off"}


def _to_int(
    value: Any,
    default: int,
    lo: Optional[int] = None,
    hi: Optional[int] = None,
    strict: bool = True,
    name: str = "value",
) -> int:
    """Convert a raw config value to an int within [lo, hi].

    In strict mode an unconvertible or out-of-range value raises ValueError.
    Otherwise it is replaced by the field default and a warning is logged.
    """
    try:
        result = int(value)
        if (lo is not None and result < lo) or (hi is not None and result > hi):
            raise ValueError(f"{name} out of range: {result}")
        return result
    except (TypeError, ValueError) as err:
        if strict:
            raise ValueError(f"Invalid {name}: {value!r}") from err
        logger.warning("Invalid %s %r in config; using default %r", name, value, default)
        return default


def _to_bool(value: Any, default: bool, strict: bool = True, name: str = "value") -> bool:
    """Convert a raw config value to a bool, understanding "true"/"false" style strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
    if strict:
        raise ValueError(f"Invalid {name}: {value!r}")
    logger.warning("Invalid %s %r in config; using default %r", name, value, default)
    return default


@dataclass
class AppCloseSchedule:
    """Controls the OS process closer bedtime and grace periods."""

    target_hour: int = 22
    target_minute: int = 0
    enabled: bool = True
    grace_period_seconds: int = 15
    force_kill_after_grace: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]], strict: bool = True) -> "AppCloseSchedule":
        if not isinstance(data, dict):
            return cls()
        return cls(
            target_hour=_to_int(data.get("target_hour", 22), 22, 0, 23, strict, "target_hour"),
            target_minute=_to_int(data.get("target_minute", 0), 0, 0, 59, strict, "target_minute"),
            enabled=_to_bool(data.get("enabled", True), True, strict, "enabled"),
            grace_period_seconds=_to_int(
                data.get("grace_period_seconds", 15), 15, 0, 300, strict, "grace_period_seconds"
            ),
            force_kill_after_grace=_to_bool(
                data.get("force_kill_after_grace", True), True, strict, "force_kill_after_grace"
            ),
        )


@dataclass
class BlockRule:
    """Controls domain blocking schedules and target domain list."""

    domains: List[str] = field(
        default_factory=lambda: [
            "reddit.com",
            "www.reddit.com",
            "youtube.com",
            "www.youtube.com",
            "x.com",
            "twitter.com",
            "instagram.com",
            "www.instagram.com",
            "tiktok.com",
            "www.tiktok.com",
        ]
    )
    trigger_type: str = "recurring"  # "recurring" | "timer"
    start_hour: int = 22
    start_minute: int = 0
    end_hour: int = 6
    end_minute: int = 0
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]], strict: bool = True) -> "BlockRule":
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        domains_raw = data.get("domains", defaults.domains)
        if not isinstance(domains_raw, (list, tuple)):
            if strict:
                raise ValueError(
                    f"BlockRule.domains must be a list, got {type(domains_raw).__name__}"
                )
            logger.warning("Invalid domains %r in config; using default list", domains_raw)
            domains_raw = defaults.domains
        return cls(
            domains=[str(d) for d in domains_raw],
            trigger_type=str(data.get("trigger_type", "recurring")),
            start_hour=_to_int(data.get("start_hour", 22), 22, 0, 23, strict, "start_hour"),
            start_minute=_to_int(data.get("start_minute", 0), 0, 0, 59, strict, "start_minute"),
            end_hour=_to_int(data.get("end_hour", 6), 6, 0, 23, strict, "end_hour"),
            end_minute=_to_int(data.get("end_minute", 0), 0, 0, 59, strict, "end_minute"),
            active=_to_bool(data.get("active", True), True, strict, "active"),
        )


@dataclass
class OverridePolicy:
    """Controls friction policy when pausing or overriding enforcement."""

    friction_type: str = "none"  # "none" | "delay" | "typing_challenge"
    cooldown_minutes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]], strict: bool = True) -> "OverridePolicy":
        if not isinstance(data, dict):
            return cls()
        return cls(
            friction_type=str(data.get("friction_type", "none")),
            cooldown_minutes=_to_int(
                data.get("cooldown_minutes", 0), 0, 0, None, strict, "cooldown_minutes"
            ),
        )


@dataclass
class ConfigProfile:
    """Root configuration container bundling all GTFB settings."""

    version: int = 1
    profile_name: str = "Default"
    app_close_schedule: AppCloseSchedule = field(default_factory=AppCloseSchedule)
    block_rules: List[BlockRule] = field(default_factory=lambda: [BlockRule()])
    override_policy: OverridePolicy = field(default_factory=OverridePolicy)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]], strict: bool = True) -> "ConfigProfile":
        """Build a profile from a raw dictionary.

        With strict=True (default) any invalid or out-of-range field raises ValueError.
        With strict=False each invalid field falls back to its own default instead,
        so the remaining valid settings are preserved.
        """
        if not isinstance(data, dict):
            return cls()

        app_close_raw = data.get("app_close_schedule")
        if isinstance(app_close_raw, AppCloseSchedule):
            app_close = app_close_raw
        elif isinstance(app_close_raw, dict):
            app_close = AppCloseSchedule.from_dict(app_close_raw, strict)
        else:
            app_close = AppCloseSchedule()

        block_rules_raw = data.get("block_rules")
        if isinstance(block_rules_raw, list) and len(block_rules_raw) > 0:
            block_rules = [
                br if isinstance(br, BlockRule) else BlockRule.from_dict(br, strict)
                for br in block_rules_raw
            ]
        else:
            block_rules = [BlockRule()]

        override_raw = data.get("override_policy")
        if isinstance(override_raw, OverridePolicy):
            override = override_raw
        elif isinstance(override_raw, dict):
            override = OverridePolicy.from_dict(override_raw, strict)
        else:
            override = OverridePolicy()

        return cls(
            version=_to_int(data.get("version", 1), 1, None, None, strict, "version"),
            profile_name=str(data.get("profile_name", "Default")),
            app_close_schedule=app_close,
            block_rules=block_rules,
            override_policy=override,
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "ConfigProfile":
        data = json.loads(json_str)
        return cls.from_dict(data)
