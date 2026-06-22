# GDLnucleus

**A lightweight, file-based development environment for ArchiCAD GDL library parts.**

GDLnucleus turns the binary `.gsm` round-trip into a clean, text-based, version-controllable
workflow. A single Python script wraps Graphisoft's `LP_XMLConverter` and gives you:

- **Decompile** `.gsm` → editable GDL scripts + `Parameters.xml` (one folder per object)
- **Compile** editable source → `.gsm` again
- **HSF / LCF** export, embedded picture updates, parameter CSV export
- Automatic multi-level **backups**, **logging**, and optional **Git auto-commit** of your source
- Ready-to-use **VS Code tasks** for every step

It is editor-agnostic at its core (just Python), with first-class VS Code integration.

---

## Requirements

- **Python 3.x** — <https://www.python.org/downloads/>
- **ArchiCAD** with `LP_XMLConverter` (ships inside the ArchiCAD installation)
- **VS Code** (optional, for the one-click tasks)

---

## Quick start

1. **Clone / download** this repository and open the folder in VS Code.
2. **Set the converter path** in `gdlconfig.json` for your platform (see below).
3. Put your library into `01_gsms/<YourLibrary>/` (the converter detects the first
   sub-folder there as the library name; macros go into `01_gsms/<YourLibrary>/Makros/`).
4. Run a task (`Terminal → Run Task…`) or call the script directly:

```bash
# Decompile every GSM into editable source (02_source/)
python3 bin/gdlconverter.py g2x --all .

# Edit the scripts in 02_source/<Object>/ …

# Compile the source back into GSM
python3 bin/gdlconverter.py x2g --all .
```

---

## Configuration — `gdlconfig.json`

Single source of truth for the toolchain. Set the `LP_XMLConverter` path under
`platforms` for your OS (the example points at ArchiCAD 28):

```json
"platforms": {
  "windows": { "lpxmlconverter": "C:\\Program Files\\Graphisoft\\ArchiCAD 28\\LP_XMLConverter.exe" },
  "mac":     { "lpxmlconverter": "/Applications/Graphisoft/AC28/ArchiCAD 28.app/Contents/MacOS/LP_XMLConverter.app/Contents/MacOS/LP_XMLConverter" }
}
```

Other keys:
- `passwords` — map of `"<gsm-name-without-extension>": "<password>"` for protected libraries.
  **Leave empty (`{}`) and never commit real passwords to a public repo.**
- `gsmbackupdirectories` — timestamped backup destinations (3 levels by default).
- `lcf` — target folder and filename for the LCF container.

---

## Folder structure

```
01_gsms/         GSM binaries you want to work on   (input; git-ignored)
   └─ <Library>/  └─ Makros/                        (macros live here)
02_source/       editable GDL + XML, one folder per object   (your source of truth)
03_bitmaps/      extracted preview bitmaps          (generated)
05_library_xml/  XML representation                 (generated)
06_library_gsm/  recompiled GSM library            (generated)
07_HSF/          Hierarchical Source Format         (generated)
11–14_…          backups                            (generated)
15_LCF/          LCF container output               (generated)
16_logs/         per-day logs                       (generated)
```

Most generated folders are created on demand — you only need to provide `01_gsms/`.

### 8-script object layout

Each object in `02_source/<Object>/` uses a fixed convention:

| File | Purpose |
|------|---------|
| `1-Master-Script.gdl` | Global constants, UI page/array init |
| `2-Parameter-Script.gdl` | `VALUES`, show/hide/lock of UI controls |
| `3-2D-Script.gdl` | 2D / floor-plan (`PROJECT2`) |
| `4-3D-Script.gdl` | 3D geometry |
| `5-Interface-Script.gdl` | UI dialog layout |
| `6-Properties-Script.gdl` | Object metadata |
| `7-Forward-Script.gdl` / `8-Backward-Script.gdl` | Migration |
| `Parameters.xml` | All parameter declarations |

---

## Command reference

```bash
python3 bin/gdlconverter.py g2x   --all .   # GSM  → source (decompile)
python3 bin/gdlconverter.py x2g   --all .   # source → GSM (compile)
python3 bin/gdlconverter.py l2hsf --all .   # GSM  → HSF
python3 bin/gdlconverter.py g2L   --all .   # build LCF container
python3 bin/gdlconverter.py images --all .  # update embedded Picture.xml
python3 bin/gdlconverter.py paramcsv --all . # export parameters to CSV
```

Replace `--all` with a single file path to process just one object.
The same commands are wrapped as VS Code tasks in `.vscode/tasks.json`.

---

## VS Code extension — GDL Parameter Editor

`extensions/gdl-parameter-editor-0.5.7.vsix` is an optional companion extension that
gives you a visual editor for `Parameters.xml`. Install it via:

```
code --install-extension extensions/gdl-parameter-editor-0.5.7.vsix
```

or in VS Code: *Extensions → … → Install from VSIX…*

---

## Notes

- Source of truth is `02_source/`; the binary/generated folders are git-ignored.
- After `g2x`, the tool can auto-commit the extracted source (commit prefix = mode name).
- Tested on macOS with ArchiCAD 28; Windows paths are supported via `gdlconfig.json`.

---

## License

Released under the [MIT License](LICENSE). © 2026 Jochen Sühlo (b-prisma).

---

*GDLnucleus — by Jochen Sühlo / b-prisma. Contributions and feedback welcome.*
