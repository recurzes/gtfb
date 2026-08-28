"""Domain models for GTFB configuration."""

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Dict, List, Optional


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
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "AppCloseSchedule":
        if not isinstance(data, dict):
            return cls()
        return cls(
            target_hour=data.get("target_hour", 22),
            target_minute=data.get("target_minute", 0),
            enabled=data.get("enabled", True),
            grace_period_seconds=data.get("grace_period_seconds", 15),
            force_kill_after_grace=data.get("force_kill_after_grace", True),
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
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BlockRule":
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        return cls(
            domains=list(data.get("domains", defaults.domains)),
            trigger_type=data.get("trigger_type", "recurring"),
            start_hour=data.get("start_hour", 22),
            start_minute=data.get("start_minute", 0),
            end_hour=data.get("end_hour", 6),
            end_minute=data.get("end_minute", 0),
            active=data.get("active", True),
        )


@dataclass
class OverridePolicy:
    """Controls friction policy when pausing or overriding enforcement."""

    friction_type: str = "none"  # "none" | "delay" | "typing_challenge"
    cooldown_minutes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "OverridePolicy":
        if not isinstance(data, dict):
            return cls()
        return cls(
            friction_type=data.get("friction_type", "none"),
            cooldown_minutes=data.get("cooldown_minutes", 0),
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
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ConfigProfile":
        if not isinstance(data, dict):
            return cls()

        app_close_raw = data.get("app_close_schedule")
        if isinstance(app_close_raw, AppCloseSchedule):
            app_close = app_close_raw
        elif isinstance(app_close_raw, dict):
            app_close = AppCloseSchedule.from_dict(app_close_raw)
        else:
            app_close = AppCloseSchedule()

        block_rules_raw = data.get("block_rules")
        if isinstance(block_rules_raw, list) and len(block_rules_raw) > 0:
            block_rules = [
                br if isinstance(br, BlockRule) else BlockRule.from_dict(br)
                for br in block_rules_raw
            ]
        else:
            block_rules = [BlockRule()]

        override_raw = data.get("override_policy")
        if isinstance(override_raw, OverridePolicy):
            override = override_raw
        elif isinstance(override_raw, dict):
            override = OverridePolicy.from_dict(override_raw)
        else:
            override = OverridePolicy()

        return cls(
            version=data.get("version", 1),
            profile_name=data.get("profile_name", "Default"),
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
