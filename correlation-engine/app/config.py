"""Load and validate the YAML asset registry."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ASSETS_YAML = Path(__file__).resolve().parent.parent / "config" / "assets.yaml"


@dataclass(frozen=True)
class AssetEntry:
    decoy_id: str
    real_asset_id: str
    real_repo_url: str
    real_tooling_url: str
    focus: str
    project_name: str
    vuln_classes_watched: list[str] = field(default_factory=list)


@dataclass
class AssetRegistry:
    assets: dict[str, AssetEntry] = field(default_factory=dict)

    def lookup(self, decoy_id: str) -> AssetEntry | None:
        return self.assets.get(decoy_id)


def load_registry(path: Path | str = ASSETS_YAML) -> AssetRegistry:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Asset registry not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    entries: dict[str, AssetEntry] = {}
    for item in raw.get("assets", []):
        entry = AssetEntry(
            decoy_id=item["decoy_id"],
            real_asset_id=item["real_asset_id"],
            real_repo_url=item.get("real_repo_url", ""),
            real_tooling_url=item.get("real_tooling_url", ""),
            focus=item.get("focus", ""),
            project_name=item.get("project_name", ""),
            vuln_classes_watched=item.get("vuln_classes_watched", []),
        )
        entries[entry.decoy_id] = entry
        logger.info("Registered asset decoy_id=%s → real_asset_id=%s", entry.decoy_id, entry.real_asset_id)

    logger.info("Loaded %d asset(s) from %s", len(entries), path)
    return AssetRegistry(assets=entries)
