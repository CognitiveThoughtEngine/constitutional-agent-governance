#!/usr/bin/env python3
"""
Deterministically normalize a setuptools sdist (`*.tar.gz`).

Some setuptools versions stamp the sdist tar members and the gzip header with
wall-clock time, so two clean builds of identical source produce different
SHA-256 hashes. This repacks the archive with:

  * members sorted by name,
  * every member's mtime pinned to SOURCE_DATE_EPOCH (default 0),
  * uid/gid/uname/gname zeroed, mode preserved,
  * USTAR format (no PAX atime/ctime headers),
  * a gzip container with mtime=0 and no embedded filename.

The result is byte-identical across independent builds of the same content, so
the reviewed artifact and the published artifact can be proven equal. Content is
never changed — only archive metadata.

Usage: python scripts/normalize_sdist.py dist/<pkg>-<ver>.tar.gz
"""
from __future__ import annotations

import gzip
import io
import os
import sys
import tarfile


def normalize(path: str) -> None:
    sde = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))

    with tarfile.open(path, "r:gz") as tf:
        members = sorted(tf.getmembers(), key=lambda m: m.name)
        payload: dict[str, bytes] = {}
        for m in members:
            if m.isfile():
                f = tf.extractfile(m)
                payload[m.name] = f.read() if f is not None else b""

    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.USTAR_FORMAT) as out:
        for m in members:
            ti = tarfile.TarInfo(name=m.name)
            ti.mtime = sde
            ti.mode = m.mode
            ti.type = m.type
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            if m.isfile():
                data = payload[m.name]
                ti.size = len(data)
                out.addfile(ti, io.BytesIO(data))
            elif m.isdir():
                ti.size = 0
                out.addfile(ti)
            else:  # links / other member types are not expected in an sdist
                ti.linkname = m.linkname
                out.addfile(ti)

    with open(path, "wb") as fh:
        gz = gzip.GzipFile(filename="", fileobj=fh, mode="wb", mtime=0)
        try:
            gz.write(tar_buf.getvalue())
        finally:
            gz.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: normalize_sdist.py <path-to-sdist.tar.gz>", file=sys.stderr)
        raise SystemExit(2)
    normalize(sys.argv[1])
    print(f"normalized {sys.argv[1]} (SOURCE_DATE_EPOCH="
          f"{os.environ.get('SOURCE_DATE_EPOCH', '0')})")
