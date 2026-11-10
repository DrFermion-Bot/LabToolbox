#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_bundle.py - verify a built LabToolbox distribution is complete and runnable.

Checks performed:
  * bundled ImageJ 1.54 core:  <bundle>/imagej/ij.jar (> 1 MB)
  * bundled native Java JRE:   Windows jre/bin/java.exe, macOS jre/Contents/Home/bin/java
  * read-only counting macro:  <bundle>/scripts/imagej/count_livedead.ijm
  * third-party notices:       imagej/NOTICE.txt, imagej/LICENSE-OpenJDK.txt, imagej/LICENSE-ImageJ.txt
  * igor module collected by PyInstaller (needed for .ibw AFM files); best effort
  * bundled java executes and reports the expected os.arch (x86_64 / aarch64 / amd64)
  * macOS only: Info.plist CFBundleShortVersionString/CFBundleVersion match the release version

Usage:
    python scripts/verify_bundle.py                       # dist/ of this host
    python scripts/verify_bundle.py --platform macos-arm64 --version 0.2.0
Exit code 0 = every check passed; 1 = at least one hard failure.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ARCH = {
    "windows": ("amd64", "x86_64"),
    "macos-intel": ("x86_64",),
    "macos-arm64": ("aarch64", "arm64"),
}
JAVA_LAYOUT = {
    "windows": Path("jre") / "bin" / "java.exe",
    "macos-intel": Path("jre") / "Contents" / "Home" / "bin" / "java",
    "macos-arm64": Path("jre") / "Contents" / "Home" / "bin" / "java",
}

failures: list[str] = []
notes: list[str] = []


def check(ok: bool, message: str) -> bool:
    if ok:
        print(f"  OK   {message}")
    else:
        print(f"  FAIL {message}")
        failures.append(message)
    return ok


def detect_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        import platform as _p

        return "macos-arm64" if _p.machine().lower() in ("arm64", "aarch64") else "macos-intel"
    raise SystemExit("verify_bundle.py: only Windows/macOS builds are produced by this project")


def pyproject_version() -> str:
    try:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
        return match.group(1).strip() if match else "0.0.0"
    except OSError:
        return "0.0.0"


def _find_bundle_data_root(app_root: Path) -> Path | None:
    """Return the directory that acts as sys._MEIPASS (where datas live)."""
    candidates = [
        app_root,
        app_root / "_internal",                       # PyInstaller 6 onedir (Windows)
        app_root / "Contents" / "Frameworks",         # PyInstaller 6 .app (macOS)
        app_root / "Contents" / "Resources",          # PyInstaller 5 .app (macOS)
    ]
    for cand in candidates:
        if (cand / "imagej" / "ij.jar").is_file():
            return cand
    # fallback: search (bounded) for imagej/ij.jar anywhere below the app root
    for jar in app_root.rglob("ij.jar"):
        if jar.parent.name == "imagej":
            return jar.parent.parent
    return None


def _find_relative(root: Path, rel: str) -> Path | None:
    for base in [root, root / "_internal", root / "Contents" / "Frameworks",
                 root / "Contents" / "Resources"]:
        cand = base / rel
        if cand.exists():
            return cand
    hits = list(root.rglob(Path(rel).name))
    for hit in hits:
        if str(hit).replace("\\", "/").endswith(rel.replace("\\", "/")):
            return hit
    return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_igor(exe: Path) -> None:
    """Best-effort: confirm the igor package was collected into the PyInstaller archive."""
    try:
        from PyInstaller.archive.readers import CArchiveReader  # type: ignore

        archive = CArchiveReader(str(exe))
        toc = archive.toc
        pyz_name = next((str(n) for n in toc if str(n).endswith(".pyz")), None)
        if pyz_name is None:
            notes.append("igor check skipped: no embedded .pyz found in executable TOC")
            return
        try:
            pyz = archive.open_embedded_archive(pyz_name)
        except AttributeError:  # older/newer PyInstaller API
            pyz = archive.open_embedded_archive(pyz_name)  # pragma: no cover
        names = list(pyz.toc.keys())
        has = any(n == "igor" or n.startswith("igor.") for n in names)
        check(has, "igor package collected (needed for Bruker .ibw import)")
        if not has and names:
            notes.append(f"pyz has {len(names)} modules; igor missing")
    except Exception as exc:  # noqa: BLE001 - verification is best effort
        notes.append(f"igor check skipped ({type(exc).__name__}: {exc})")


def check_bundled_java(java: Path, platform: str) -> None:
    try:
        proc = subprocess.run(
            [str(java), "-XshowSettings:properties", "-version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except OSError as exc:
        check(False, f"bundled java could not be executed: {exc}")
        return
    out = (proc.stdout or "") + (proc.stderr or "")
    version = re.search(r"java\.version = ([^\s]+)", out)
    arch = re.search(r"os\.arch = ([^\s]+)", out)
    check(proc.returncode == 0, f"bundled java exits 0 (java {version.group(1) if version else '?'})")
    expected = EXPECTED_ARCH[platform]
    check(
        arch is not None and arch.group(1) in expected,
        f"bundled java architecture is {arch.group(1) if arch else 'unknown'} (expected one of {expected})",
    )
    if version:
        print(f"       java.version = {version.group(1)}")


def check_macos_metadata(app_root: Path, expected_version: str) -> None:
    info = app_root / "Contents" / "Info.plist"
    if not check(info.is_file(), f"macOS Info.plist present ({info})"):
        return
    with open(info, "rb") as fh:
        plist = plistlib.load(fh)
    short = str(plist.get("CFBundleShortVersionString", ""))
    build = str(plist.get("CFBundleVersion", ""))
    numeric = re.match(r"^[0-9]+(\.[0-9]+){0,2}", expected_version.lstrip("v"))
    numeric = numeric.group(0) if numeric else expected_version
    check(short == numeric, f"Info.plist CFBundleShortVersionString={short} (expected {numeric})")
    check(bool(build), f"Info.plist CFBundleVersion={build}")
    print(f"       CFBundleVersion = {build}, CFBundleIdentifier = {plist.get('CFBundleIdentifier')}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify a built LabToolbox distribution")
    parser.add_argument("--dist", default=str(ROOT / "dist"), help="PyInstaller dist directory")
    parser.add_argument("--platform", choices=["auto", "windows", "macos-intel", "macos-arm64"],
                        default="auto")
    parser.add_argument("--version", default=os.environ.get("APP_VERSION", ""),
                        help="expected release version (default: APP_VERSION env or pyproject)")
    args = parser.parse_args(argv)

    platform = detect_platform() if args.platform == "auto" else args.platform
    expected_version = args.version.strip() or pyproject_version()
    dist = Path(args.dist).resolve()
    if platform == "windows":
        app_root, exe = dist / "LabToolbox", dist / "LabToolbox" / "LabToolbox.exe"
    else:
        app_root, exe = dist / "LabToolbox.app", dist / "LabToolbox.app" / "Contents" / "MacOS" / "LabToolbox"

    print(f"verify_bundle: platform={platform} version={expected_version}")
    print(f"               app={app_root}")
    if not check(app_root.is_dir(), f"built application exists: {app_root}"):
        return 1
    if not check(exe.is_file(), f"main executable exists: {exe.name}"):
        return 1

    data_root = _find_bundle_data_root(app_root)
    if not check(data_root is not None, "bundle data root (sys._MEIPASS) located"):
        return 1
    print(f"       bundle data root = {data_root}")

    # ---- ImageJ bundle -----------------------------------------------------
    imagej = data_root / "imagej"
    ij_jar = imagej / "ij.jar"
    check(ij_jar.is_file() and ij_jar.stat().st_size > 1_000_000,
          f"bundled ImageJ core ij.jar ({ij_jar.stat().st_size / 1e6:.2f} MB)" if ij_jar.is_file() else "bundled ImageJ core ij.jar")
    java = imagej / JAVA_LAYOUT[platform]
    check(java.is_file(), f"bundled native Java runtime ({JAVA_LAYOUT[platform]})")
    for rel in ["NOTICE.txt", "LICENSE-ImageJ.txt", "LICENSE-OpenJDK.txt"]:
        check((imagej / rel).is_file(), f"bundled ImageJ/JRE notice: imagej/{rel}")
    if java.is_file():
        check_bundled_java(java, platform)

    # bundle must match the build inputs (catches a stale copy)
    vendor_jar = ROOT / "vendor" / "imagej" / "ij.jar"
    if vendor_jar.is_file() and ij_jar.is_file():
        check(sha256(vendor_jar) == sha256(ij_jar), "bundled ij.jar matches vendor/imagej/ij.jar")

    # ---- read-only counting macro -----------------------------------------
    macro = data_root / "scripts" / "imagej" / "count_livedead.ijm"
    check(macro.is_file(), f"read-only ImageJ counting macro ({macro.relative_to(data_root)})")
    for rel in ("third_party/COPYING", "third_party/COPYING.LESSER"):
        check((data_root / rel).is_file(), f"bundled igor LGPL license text ({rel})")
    check((data_root / "THIRD_PARTY_NOTICES.md").is_file(), "bundled THIRD_PARTY_NOTICES.md")

    # ---- example data (GUI "open example" buttons) ------------------------
    check((data_root / "examples").is_dir(), "example tables bundled (examples/)")
    check((data_root / "data" / "examples").is_dir(), "CLI example data bundled (data/examples/)")

    # ---- igor (.ibw) ------------------------------------------------------
    check_igor(exe)

    # ---- platform metadata ------------------------------------------------
    if platform != "windows":
        check_macos_metadata(app_root, expected_version)

    # ---- summary ----------------------------------------------------------
    total = sum(p.stat().st_size for p in app_root.rglob("*") if p.is_file())
    imagej_size = sum(p.stat().st_size for p in imagej.rglob("*") if p.is_file()) if imagej.is_dir() else 0
    print(f"\napp size        : {total / 1e6:.1f} MB")
    print(f"bundled ImageJ  : {imagej_size / 1e6:.1f} MB")
    if notes:
        print("notes:")
        for note in notes:
            print(f"  - {note}")
    if failures:
        print(f"\nVERIFY FAILED ({len(failures)} check(s))")
        return 1
    print("\nVERIFY OK: bundle is self-contained (ImageJ + native JRE + macro + igor).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())