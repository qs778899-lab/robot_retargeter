"""PNS/PNL-style BVH source discovery."""

from __future__ import annotations

from pathlib import Path

from .base import SourceMotion
from .discovery import discover_bvh_sources

DEFAULT_PNS_ROOT = Path("dataset/human_bvh/pns")


def discover(
    *,
    task: str | None = None,
    input_bvh: Path | None = None,
    input_dir: Path | None = None,
    input_root: Path = DEFAULT_PNS_ROOT,
) -> list[SourceMotion]:
    return discover_bvh_sources(
        source_format="pns_bvh",
        input_bvh=input_bvh,
        input_dir=input_dir,
        task=task,
        input_root=input_root,
    )
