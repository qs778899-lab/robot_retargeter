"""Common BVH source discovery helpers."""

from __future__ import annotations

from pathlib import Path

from .base import SourceMotion

INTERMEDIATE_SUFFIXES = ("_soma", "_trimmed", "_tpose", "_armtwist")


def is_intermediate_bvh(path: Path) -> bool:
    return any(path.stem.endswith(suffix) for suffix in INTERMEDIATE_SUFFIXES)


def discover_bvh_sources(
    *,
    source_format: str,
    input_bvh: Path | None = None,
    input_dir: Path | None = None,
    task: str | None = None,
    input_root: Path | None = None,
) -> list[SourceMotion]:
    if input_bvh is not None:
        bvh = input_bvh.expanduser().resolve()
        if not bvh.is_file():
            raise FileNotFoundError(f"BVH file not found: {bvh}")
        return [
            SourceMotion(
                motion_bvh=bvh,
                output_stem=bvh.stem,
                source_format=source_format,
                display_name=bvh.name,
            )
        ]

    if input_dir is not None:
        bvh_dir = input_dir.expanduser().resolve()
    else:
        if task is None or input_root is None:
            raise ValueError("Either input_bvh, input_dir, or task + input_root is required")
        bvh_dir = input_root.expanduser().resolve() / task

    if not bvh_dir.is_dir():
        raise FileNotFoundError(f"BVH directory not found: {bvh_dir}")

    return [
        SourceMotion(
            motion_bvh=bvh,
            output_stem=bvh.stem,
            source_format=source_format,
            display_name=bvh.name,
        )
        for bvh in sorted(bvh_dir.glob("*.bvh"))
        if not is_intermediate_bvh(bvh)
    ]
