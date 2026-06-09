#!/usr/bin/env python3
"""Build the Agent Kit provenance bundle with deterministic tar metadata."""

from __future__ import annotations

import argparse
import gzip
import tarfile
from pathlib import Path


def build_bundle(root: str | Path, output: str | Path) -> None:
    """Create a gzipped tar bundle for the catalog provenance files."""

    root_path = Path(root)
    output_path = Path(output)
    members = (
        Path("manifest.json"),
        Path("dist/provenance/agent-kit-catalog.intoto.json"),
        Path("dist/provenance/manifest.sha256"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as archive:
                for relative in members:
                    path = root_path / relative
                    info = archive.gettarinfo(str(path), arcname=str(relative))
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with path.open("rb") as fileobj:
                        archive.addfile(info, fileobj)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path("."), type=Path, help="Catalog root")
    parser.add_argument("--output", required=True, type=Path, help="Output .tgz path")
    args = parser.parse_args(argv)

    build_bundle(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
