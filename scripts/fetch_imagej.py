#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_imagej.py — assemble the self-contained ImageJ bundle shipped with LabToolbox.

Downloads the *official* ImageJ 1.54 distribution (for ij.jar) and a native
Eclipse Temurin 11 JRE (for the platform), then normalizes them into a single
directory that PyInstaller embeds as ``imagej/``:

    vendor/imagej/
    ├── ij.jar                          ImageJ 1.54 core (unmodified, from wsr.imagej.net)
    ├── jre/bin/java.exe                Windows x64
    ├── jre/Contents/Home/bin/java      macOS Intel / Apple Silicon (native arch)
    ├── LICENSE-ImageJ.txt              ImageJ attribution / licensing note
    ├── LICENSE-OpenJDK.txt             GPLv2 + Classpath Exception (from the JRE)
    ├── NOTICE.txt                      provenance: URLs, versions, SHA-256
    └── NOTICE-OpenJDK.txt              upstream OpenJDK NOTICE

Why not the JRE that comes with the official zips?
  * ij154-win-java8.zip ships a Java 8 JRE (works, but EOL).
  * ij154-osx-java8.zip ships an **x86_64-only** Zulu 8 JRE, so it cannot run
    natively on Apple Silicon. We therefore use Eclipse Temurin 11 for every
    platform (verified: ImageJ 1.54 Analyze Particles runs on Java 11).
No runtime download happens in the packaged app: everything is embedded.

Usage:
    python scripts/fetch_imagej.py                    # auto-detect host platform
    python scripts/fetch_imagej.py --platform windows
    python scripts/fetch_imagej.py --platform macos-arm64
    python scripts/fetch_imagej.py --cache-dir vendor/.downloads --out vendor/imagej

Downloads are cached in --cache-dir so repeated local builds are fast.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform as _platform
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Upstream sources (official ImageJ distros + Adoptium Temurin GA binaries)
# --------------------------------------------------------------------------- #
IMAGEJ_VERSION = "1.54"
IMAGEJ_SOURCES = {
    "windows": {
        "url": "https://wsr.imagej.net/distros/win/ij154-win-java8.zip",
        "filename": "ij154-win-java8.zip",
    },
    "macos": {
        "url": "https://wsr.imagej.net/distros/osx/ij154-osx-java8.zip",
        "filename": "ij154-osx-java8.zip",
    },
}
JAVA_FEATURE_VERSION = "11"
TEMURIN_URL = (
    "https://api.adoptium.net/v3/binary/latest/{java}/ga/{os}/{arch}/jre/hotspot/normal/eclipse"
)
TEMURIN_SOURCES = {
    "windows": {
        "os": "windows",
        "arch": "x64",
        "filename": "temurin11-win-x64-jre.zip",
        "kind": "zip",
    },
    "macos-intel": {
        "os": "mac",
        "arch": "x64",
        "filename": "temurin11-mac-x64-jre.tar.gz",
        "kind": "tar.gz",
    },
    "macos-arm64": {
        "os": "mac",
        "arch": "aarch64",
        "filename": "temurin11-mac-arm64-jre.tar.gz",
        "kind": "tar.gz",
    },
}

PLATFORM_LABEL = {
    "windows": "Windows x64",
    "macos-intel": "macOS Intel (x86_64)",
    "macos-arm64": "macOS Apple Silicon (arm64)",
}

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(msg, flush=True)


def detect_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos-arm64" if _platform.machine().lower() in ("arm64", "aarch64") else "macos-intel"
    raise SystemExit(
        "fetch_imagej.py: unsupported build host %r (LabToolbox ships Windows/macOS builds only)"
        % (sys.platform,)
    )


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def download(url: str, dest: Path, refresh: bool = False) -> Path:
    """Download ``url`` to ``dest`` (follows redirects), skipping if cached."""
    if dest.exists() and dest.stat().st_size > 0 and not refresh:
        log(f"  cached: {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"  downloading {dest.name}\n    <- {url}")
    started = time.time()
    last_note = 0.0
    # Adoptium's API rejects the default Python-urllib User-Agent with HTTP 403.
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "LabToolbox-build/1.0 (+https://github.com/DrFermion/LabToolbox)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last_note > 5:
                last_note = now
                pct = f"{100.0 * done / total:.0f}%" if total else "?"
                log(f"    {done / 1e6:.1f} MB ({pct})")
    tmp.replace(dest)
    log(f"    done in {time.time() - started:.0f}s, {dest.stat().st_size / 1e6:.1f} MB")
    return dest


def _pick_shallowest(names, predicate):
    hits = [n for n in names if predicate(n)]
    if not hits:
        return None
    return min(hits, key=lambda n: (n.count("/"), len(n)))


def extract_imagej_jar(imagej_zip: Path, out_dir: Path) -> tuple[Path, str]:
    """Extract the ImageJ core ij.jar from the official distribution zip."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "ij.jar"
    with zipfile.ZipFile(imagej_zip) as zf:
        member = _pick_shallowest(
            zf.namelist(), lambda n: n.rstrip("/").endswith("/ij.jar") or n == "ij.jar"
        )
        if member is None:
            raise SystemExit(f"ij.jar not found inside {imagej_zip.name}")
        with zf.open(member) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return target, member


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)


def _find_jre_root(extracted: Path, platform: str) -> tuple[Path, Path]:
    """Return (jre_bundle_root, java_executable) inside an extracted Temurin archive."""
    if platform == "windows":
        candidates = [p for p in extracted.rglob("bin/java.exe") if p.is_file()]
        if not candidates:
            raise SystemExit("java.exe not found in Temurin Windows JRE archive")
        java = min(candidates, key=lambda p: len(p.parts))
        return java.parent.parent, java
    candidates = [p for p in extracted.rglob("Contents/Home/bin/java") if p.is_file()]
    if not candidates:
        raise SystemExit("Contents/Home/bin/java not found in Temurin macOS JRE archive")
    java = min(candidates, key=lambda p: len(p.parts))
    bundle = java.parents[3]  # .../<name>.jre/Contents/Home/bin/java -> <name>.jre
    return bundle, java


def assemble_jre(jre_archive: Path, out_dir: Path, platform: str) -> tuple[Path, Path]:
    """Normalize the Temurin JRE into out_dir/jre with the platform contract layout."""
    with tempfile.TemporaryDirectory(prefix="labtoolbox-jre-") as tmp:
        tmp_path = Path(tmp)
        if platform == "windows":
            with zipfile.ZipFile(jre_archive) as zf:
                zf.extractall(tmp_path)
        else:
            with tarfile.open(jre_archive, "r:gz") as tf:
                tf.extractall(tmp_path)
        bundle, java = _find_jre_root(tmp_path, platform)
        _copytree(bundle, out_dir)
    if platform == "windows":
        java_out = out_dir / "bin" / "java.exe"
    else:
        java_out = out_dir / "Contents" / "Home" / "bin" / "java"
    if not java_out.is_file():
        raise SystemExit(f"JRE normalization failed: {java_out} missing")
    return out_dir, java_out


def copy_licenses(jre_dir: Path, platform: str, bundle_dir: Path) -> None:
    """Copy the OpenJDK license/NOTICE files next to ij.jar."""
    if platform == "windows":
        home = jre_dir
    else:
        home = jre_dir / "Contents" / "Home"
    notice = home / "NOTICE"
    if notice.is_file():
        shutil.copy2(notice, bundle_dir / "NOTICE-OpenJDK.txt")
    license_file = home / "legal" / "java.base" / "LICENSE"
    if license_file.is_file():
        shutil.copy2(license_file, bundle_dir / "LICENSE-OpenJDK.txt")
    # Java 11 JREs have no top-level LICENSE; also ship release metadata.
    release = home / "release"
    if release.is_file():
        shutil.copy2(release, bundle_dir / "JRE-release.txt")


def read_jre_version(jre_dir: Path, platform: str) -> str:
    home = jre_dir if platform == "windows" else jre_dir / "Contents" / "Home"
    release = home / "release"
    if not release.is_file():
        return "unknown"
    text = release.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'JAVA_VERSION="?([^"\n]+)"?', text)
    return match.group(1).strip() if match else "unknown"


IMAGEJ_LICENSE_NOTE = """\
ImageJ 1.54 (ij.jar) bundled with LabToolbox
============================================

ij.jar in this directory is the unmodified ImageJ 1.54 core distribution from
the official ImageJ download site (https://wsr.imagej.net/, mirrored from
https://imagej.net/ij/). LabToolbox uses it only as an optional external
counting engine (LIVE/DEAD "Analyze Particles" pipeline, see
scripts/imagej/count_livedead.ijm).

ImageJ 1.x is developed by Wayne Rasband at the US National Institutes of
Health (NIH) and has historically been distributed as public-domain software.
For the authoritative licensing statement and how to cite ImageJ
(Schneider, Rasband & Eliceiri, Nat. Methods 9, 671-675, 2012,
https://doi.org/10.1038/nmeth.2089), see https://imagej.net/.

The ImageJ name and logo belong to their respective owners. This file is a
provenance note; see NOTICE.txt for exact download URLs and SHA-256 checksums.
"""


def write_notice(
    bundle_dir: Path,
    platform: str,
    imagej_zip: Path,
    ij_jar: Path,
    jre_archive: Path,
    jre_version: str,
) -> None:
    imagej_url = IMAGEJ_SOURCES["windows" if platform == "windows" else "macos"]["url"]
    temurin = TEMURIN_SOURCES[platform]
    temurin_url = TEMURIN_URL.format(java=JAVA_FEATURE_VERSION, os=temurin["os"], arch=temurin["arch"])
    note = f"""\
LabToolbox bundled ImageJ + Java runtime
=======================================

Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
Platform:  {PLATFORM_LABEL[platform]}
Assembled by: scripts/fetch_imagej.py (no files modified beyond normalization)

ImageJ core
-----------
  ij.jar version : {IMAGEJ_VERSION}
  source archive : {imagej_zip.name}
  source URL     : {imagej_url}
  archive SHA256 : {sha256_file(imagej_zip)}
  ij.jar SHA256  : {sha256_file(ij_jar)}

Java runtime (Eclipse Temurin, Adoptium)
----------------------------------------
  version        : Java {jre_version} (feature release {JAVA_FEATURE_VERSION})
  distribution   : Eclipse Temurin JRE {JAVA_FEATURE_VERSION} ({PLATFORM_LABEL[platform]})
  source archive : {jre_archive.name}
  source URL     : {temurin_url}
  archive SHA256 : {sha256_file(jre_archive)}

Files
-----
  ij.jar                 ImageJ {IMAGEJ_VERSION} core (unmodified)
  jre/                   Eclipse Temurin {JAVA_FEATURE_VERSION} JRE, platform-native
  LICENSE-ImageJ.txt     ImageJ attribution / licensing note
  LICENSE-OpenJDK.txt    OpenJDK GPLv2 + Classpath Exception license text
  NOTICE-OpenJDK.txt     OpenJDK NOTICE file
  JRE-release.txt        Java runtime release metadata
  NOTICE.txt             this file

Everything above is embedded in the LabToolbox installer / DMG at build time.
The packaged application never downloads ImageJ or Java at run time.
"""
    (bundle_dir / "NOTICE.txt").write_text(note, encoding="utf-8")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assemble vendor/imagej for LabToolbox builds")
    parser.add_argument(
        "--platform",
        choices=["auto", "windows", "macos-intel", "macos-arm64"],
        default="auto",
        help="target platform of the build (default: auto = this host)",
    )
    parser.add_argument("--out", default=str(ROOT / "vendor" / "imagej"), help="output directory")
    parser.add_argument(
        "--cache-dir", default=str(ROOT / "vendor" / ".downloads"), help="download cache"
    )
    parser.add_argument("--refresh", action="store_true", help="re-download cached archives")
    args = parser.parse_args(argv)

    platform = args.platform
    if platform == "auto":
        try:
            platform = detect_platform()
        except SystemExit as exc:
            print(str(exc.args[0]) if exc.args else "unsupported platform", file=sys.stderr)
            return 2
    out_dir = Path(args.out).resolve()
    cache_dir = Path(args.cache_dir).resolve()

    log(f"fetch_imagej: target={PLATFORM_LABEL[platform]} out={out_dir}")
    log("[1/3] official ImageJ {v} distribution".format(v=IMAGEJ_VERSION))
    ij_src = IMAGEJ_SOURCES["windows" if platform == "windows" else "macos"]
    imagej_zip = download(ij_src["url"], cache_dir / ij_src["filename"], args.refresh)

    log("[2/3] Eclipse Temurin {v} JRE".format(v=JAVA_FEATURE_VERSION))
    t = TEMURIN_SOURCES[platform]
    temurin_url = TEMURIN_URL.format(java=JAVA_FEATURE_VERSION, os=t["os"], arch=t["arch"])
    jre_archive = download(temurin_url, cache_dir / t["filename"], args.refresh)

    log("[3/3] normalizing into {out}".format(out=out_dir))
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    ij_jar, member = extract_imagej_jar(imagej_zip, out_dir)
    log(f"  ij.jar <- {member} ({ij_jar.stat().st_size / 1e6:.2f} MB)")
    jre_dir, java = assemble_jre(jre_archive, out_dir / "jre", platform)
    log(f"  jre    -> {java.relative_to(out_dir)}")
    copy_licenses(jre_dir, platform, out_dir)
    jre_version = read_jre_version(jre_dir, platform)
    (out_dir / "LICENSE-ImageJ.txt").write_text(IMAGEJ_LICENSE_NOTE, encoding="utf-8")
    write_notice(out_dir, platform, imagej_zip, ij_jar, jre_archive, jre_version)

    total = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    log(f"OK: {out_dir} ({total / 1e6:.1f} MB, {sum(1 for p in out_dir.rglob('*') if p.is_file())} files)")
    log(f"    ij.jar    {ij_jar}")
    log(f"    java      {java}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
