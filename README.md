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

## Why?

Visual Studio Code is a superb, highly customizable editor — and Graphisoft ships a
[GDL syntax extension](https://marketplace.visualstudio.com/items?itemName=GRAPHISOFT.gdl)
with full highlighting, snippets and autocomplete. What is missing is a *direct link to
ArchiCAD*. Rather than going through the API, GDLnucleus establishes an **indirect link**:
GDL objects are transferred between ArchiCAD and VS Code through Graphisoft's
`LP_XMLConverter`. A task system automates every conversion step at the push of a button,
so you can switch between ArchiCAD and VS Code at any time without losses and edit GDL
**in parallel** in both.

## Requirements

- **Python 3.x** — <https://www.python.org/downloads/>
- **ArchiCAD** with `LP_XMLConverter` (ships inside the ArchiCAD installation)
- **VS Code** + the official [Graphisoft GDL extension](https://marketplace.visualstudio.com/items?itemName=GRAPHISOFT.gdl) (syntax highlighting, snippets, autocomplete)

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

## Typical workflow (round-trip)

1. **In ArchiCAD:** create your GSM(s) (each with its own GUID, parameters, scripts) and
   save them into `01_gsms/<YourLibrary>/` (macros go into the `Makros/` sub-folder).
   *Always save in ArchiCAD first — unsaved GSMs are not covered by the backup.*
2. **Decompile:** run **GSM2XML** (`g2x`). Every object appears in `02_source/<Object>/`
   with its individual scripts and parameter list; the previous XML is backed up.
3. **Edit** the `.gdl` scripts in VS Code. Transferring parameters between objects is much
   faster directly in `Parameters.xml`.
4. **Compile back:** run **XML2GSM** (`x2g`). The scripts are reassembled into one XML and
   converted to a GSM; the old GSM is backed up with a timestamp.
5. **In ArchiCAD:** hit *Reload Libraries* — your VS Code changes are live.

Switching back to VS Code after further ArchiCAD edits? Save the GSM in ArchiCAD, then run
**GSM2XML** again. You can keep bouncing between both tools indefinitely.

### Auto-convert on save (optional)

Install the third-party extension **Trigger Task on Save** and add this to your
`settings.json` to run `XML2GSM` automatically whenever you save a `.gdl` file:

```json
"triggerTaskOnSave.tasks": {
  "XML2GSM (all files)": ["02_source/**/*.gdl"]
}
```

### Embedding graphics

1. Add a preview image to the GSM in ArchiCAD, then run **GSM2XML**.
2. The preview lands in a sub-folder of `03_bitmaps/`. Put any further images that belong
   to the object into the same folder.
3. Run **Update Picture.xml** (`images`) — the bitmaps are written into `GDLPict.xml`.
4. The next **XML2GSM** embeds them into the GSM.

### Parameter list as CSV

Run **Parameter-CSV** (`paramcsv`); the output is written to the documentation folder.

---

## VS Code extensions

Two companion extensions are bundled in `extensions/`. Install either via
`code --install-extension extensions/<file>.vsix` or in VS Code:
*Extensions → … → Install from VSIX…*

### GDL Task Runner (recommended)

`extensions/gdl-task-runner-1.0.5.vsix` shows the tasks from `.vscode/tasks.json`
as a clickable **tree view** in the Explorer — run any conversion with a single click,
automatically grouped by the comment headers in `tasks.json`. This is the most
convenient way to drive the GDLnucleus workflow.

```
code --install-extension extensions/gdl-task-runner-1.0.5.vsix
```

After installing, open this folder as a workspace and find the **GDL Tasks** section
in the Explorer panel.

### GDL Parameter Editor

`extensions/gdl-parameter-editor-0.5.7.vsix` gives you a visual editor for
`Parameters.xml`.

```
code --install-extension extensions/gdl-parameter-editor-0.5.7.vsix
```

### Also recommended (from the VS Code Marketplace)

- **[Graphisoft GDL](https://marketplace.visualstudio.com/items?itemName=GRAPHISOFT.gdl)** — official GDL syntax highlighting, snippets and autocomplete (essential).
- **Trigger Task on Save** — run `XML2GSM` automatically on save (see *Auto-convert on save* above).

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
