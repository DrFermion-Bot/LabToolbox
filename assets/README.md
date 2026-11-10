# App icons · 应用图标

| File | Used for |
|---|---|
| `labtoolbox.ico` | Windows EXE icon + Inno Setup installer/shortcuts |
| `labtoolbox.icns` | macOS `.app` bundle icon |
| `labtoolbox.png` | 1024×1024 master image (documentation / other tools) |

These are **replaceable placeholders**. `labtoolbox.spec` picks up whatever
`assets/labtoolbox.ico` / `assets/labtoolbox.icns` exist at build time, and
`installer.iss` uses `assets/labtoolbox.ico` (`SetupIconFile`).

## Replacing them

1. Overwrite `labtoolbox.ico` with a real Windows icon (16–256 px, 32-bit) and
   `labtoolbox.icns` with a macOS icon (PNG-based ICNS, 16–1024 px).
   Keep the same file names — nothing else needs to change.
2. Optional: also replace `labtoolbox.png` with your 1024×1024 master.
3. Rebuild with `pyinstaller labtoolbox.spec --noconfirm`.

To regenerate all three files from the built-in placeholder artwork (requires
Pillow):

```bash
python scripts/build_icons.py
```

## Design / license

The placeholder artwork (flask + gradient) was generated for this project by
`scripts/build_icons.py` and is MIT-licensed like the rest of the repository.
It is intentionally simple so it can be swapped for e.g. the University of
Dundee / lab logo without touching build configuration.