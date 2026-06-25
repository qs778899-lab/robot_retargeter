"""v3 BVH source discovery."""

from __future__ import annotations

import re
from pathlib import Path

from .base import SourceMotion
from .discovery import discover_bvh_sources

DEFAULT_V3_ROOT = Path("dataset/human_bvh/v3")


def discover(
    *,
    task: str | None = None,
    input_bvh: Path | None = None,
    input_dir: Path | None = None,
    input_root: Path = DEFAULT_V3_ROOT,
) -> list[SourceMotion]:
    sources = discover_bvh_sources(
        source_format="v3_bvh",
        input_bvh=input_bvh,
        input_dir=input_dir,
        task=task,
        input_root=input_root,
    )
    return [_with_v3_metadata(source) for source in sources]


def _with_v3_metadata(source: SourceMotion) -> SourceMotion:
    parse_stem = re.sub(r"-v\d+$", "", source.motion_bvh.stem)
    if "-" not in parse_stem:
        return source
    base, _, person = parse_stem.rpartition("-")
    if not base or not person:
        return source
    return SourceMotion(
        motion_bvh=source.motion_bvh,
        output_stem=source.output_stem,
        source_format=source.source_format,
        display_name=source.display_name,
        base=base,
        person=person,
    )
