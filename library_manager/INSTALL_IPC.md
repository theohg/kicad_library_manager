## KiCad Library Manager (KiCad 9 IPC plugin) — Install

This plugin uses KiCad 9's **IPC plugin** system (not the legacy SWIG Action Plugin system).

### 0) Prerequisites

- **KiCad 9.x**
- **IPC API server enabled** in pcbnew preferences (API / IPC section).
- **Python interpreter** set in KiCad preferences (Linux typically `/usr/bin/python3`; macOS/Windows typically KiCad's bundled Python).

### 1) Find your KiCad documents home

In **pcbnew** go to `Preferences → Configure Paths` and note `KICAD_DOCUMENTS_HOME`.

Your IPC plugins directory is:

- `${KICAD_DOCUMENTS_HOME}/9.0/plugins/`

### 2) Install the plugin bundle (symlink)

This IPC plugin bundle contains:

- `library_manager/` (main UI)
- `kicad_footprint_generator/` (generator, launched from the UI)

#### Linux

```bash
mkdir -p "$HOME/.local/share/kicad/9.0/plugins" \
  && rm -rf "$HOME/.local/share/kicad/9.0/plugins/kicad_library_manager" \
  && ln -s "/path/to/your/repo/kicad_plugin" \
    "$HOME/.local/share/kicad/9.0/plugins/kicad_library_manager"
```

If your `KICAD_DOCUMENTS_HOME` is different, replace the `~/.local/share/kicad` part accordingly.

#### macOS (example)

```bash
mkdir -p "$HOME/Documents/KiCad/9.0/plugins" \
  && rm -rf "$HOME/Documents/KiCad/9.0/plugins/kicad_library_manager" \
  && ln -s "/path/to/your/repo/kicad_plugin" \
    "$HOME/Documents/KiCad/9.0/plugins/kicad_library_manager"
```

#### Windows (PowerShell, example)

```powershell
$dest = "$HOME\Documents\KiCad\9.0\plugins\kicad_library_manager"
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
New-Item -ItemType SymbolicLink -Path $dest -Target "C:\path\to\your\repo\kicad_plugin" | Out-Null
```

### 3) Restart pcbnew

Close and reopen **PCB Editor (pcbnew)**.

KiCad will create a per-plugin virtualenv under:

- Linux: `~/.cache/kicad/9.0/python-environments/<plugin-id>/`
- macOS: `~/Library/Caches/KiCad/9.0/python-environments/<plugin-id>/`
- Windows: `%LOCALAPPDATA%\KiCad\9.0\python-environments\<plugin-id>\`

### 4) Run it

In **pcbnew** open a board, then:

- `Tools → External Plugins → KiCad Library Manager`

### Notes (dependencies)

KiCad will install Python requirements listed in `requirements.txt` next to `plugin.json`:

- `kicad-python` (IPC client / `kipy`)
- `wxPython`
- `rapidfuzz`

