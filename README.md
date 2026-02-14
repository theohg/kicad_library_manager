### KiCad Library Manager

An IPC plugin for KiCad for managing local database (sqlite libraries) across many users with a nice UI.

- submit part/category requests via GitHub (`Requests/*.json`)
- fetch/sync a local clone/submodule
- browse/edit parts and browse symbols/footprints with previews
- initialize a brand-new database repo with the required CI scaffolding

**Requirements:** Python 3.12+ (bundled with KiCad 9)

---

### 1) Install the plugin

#### Recommended: KiCad Plugin and Content Manager (PCM)

1. In KiCad, open **Plugin and Content Manager**
2. Click **Manage...** (bottom left)
3. Add the following repository URL:
   ```
   https://nguyen-v.github.io/kicad_library_manager/repository.json
   ```
4. In the repository dropdown, select **nguyen-v's KiCad PCM repository**
5. Under **Plugins**, find **KiCad Library Manager** and click **Install**
6. Click **Apply Pending Changes**
7. Restart KiCad

The plugin is available under **Tools → External Plugins → KiCad Library Manager**.

#### Alternative: manual install

Install by copying (or symlinking) the **entire** `kicad_library_manager/` folder into your KiCad IPC plugins directory
(the folder that will contain `plugin.json`).

KiCad's IPC plugins directory is typically under your KiCad documents home, e.g.:

- **Linux**: `~/.local/share/kicad/9.0/plugins/`
- **macOS**: `~/Documents/KiCad/9.0/plugins/`
- **Windows**: `%USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\`

##### Linux / macOS (symlink recommended during development)

```bash
# Replace PLUGDIR with your KiCad IPC plugins directory.
PLUGDIR="$HOME/.local/share/kicad/9.0/plugins"
mkdir -p "$PLUGDIR"
ln -sfn "$(pwd)" "$PLUGDIR/kicad_library_manager"
```

##### Windows (copy recommended)

Copy this `kicad_library_manager/` folder into your KiCad IPC plugins folder.

Restart KiCad. The plugin is available under **Tools → External Plugins → KiCad Library Manager**
(menu location may vary slightly between editors).

---

### 2) Set up / select the database repo

You can use any GitHub repo that contains (or will contain) a KiCad library database layout:

- `Database/` (`db-*.csv`, `parts.sqlite`, `*.kicad_dbl`)
- `Requests/` (request JSON files)
- `Symbols/` and `Footprints/`

Recommended: add your database repo to each project as a submodule under `<project>/Libraries/...`.

---

### 3) Configure the plugin (Settings…)

Open the plugin, then click **Settings…** and set:

- **Local database path**: your local clone/submodule of the database repo
- **Remote database URL**: a git URL or `OWNER/REPO`
- **Branch**: usually `main`
- **DBL filename**: the `Database/*.kicad_dbl` filename to use when initializing a new repo (existing repos can keep any name)

If you created an empty repo for your database, click:

- **Initialize database repo…** (safe-by-default: creates missing files only, never overwrites existing files)  
  It will add workflows + tools + seed files, then commit+push to `origin`.

---

### 3b) Configure KiCad libraries (DBL, symbols, footprints)

This plugin manages a *KiCad database repo*, but KiCad still needs to be told about the libraries it should use.

- **Add the database (DBL) as a Symbol Library**:
  - KiCad → **Preferences → Manage Symbol Libraries…**
  - Add a new library that points to your repo's `Database/*.kicad_dbl` (KiCad "Database Library" / DBL).
- **Add the dependent symbol + footprint libraries**:
  - KiCad → **Preferences → Manage Symbol Libraries…**: add the repo's symbol libraries under `Symbols/` (and any other symbol libraries your database rows reference).
  - KiCad → **Preferences → Manage Footprint Libraries…**: add the repo's footprint libraries under `Footprints/` (and any other footprint libraries your database rows reference).
- **3D models are not generated**:
  - The bundled footprint generator generates `.kicad_mod` footprints only. It does **not** create 3D models.
  - If you want 3D models, add them externally (e.g. step/wrl files + set the 3D model references in KiCad).
- **Footprint generator notes (IPC-7351 / solder goals)**:
  - The footprint generator currently uses IPC-7351-style calculations with solder joint goals defined by PCB Libraries' Footprint Expert tables to meet J-STD-001. See: [Solder Joint Goal Tables (Footprint Expert user guide)](https://www.pcblibraries.com/products/fpx/userguide/default.asp?ch=1.7)
  - It is under active development; **not all package types shown in the dropdown are supported yet**.

---

### 4) GitHub authentication (request submission)

The plugin submits request files using the GitHub API. This is separate from your normal
`git push`/`pull` credentials — the GitHub REST API requires its own token.

The plugin looks for a token in this order:

1. `GITHUB_TOKEN` or `KICAD_LIBRARY_MANAGER_GITHUB_TOKEN` environment variable
2. `gh auth token` (GitHub CLI)
3. GitHub CLI config file (`~/.config/gh/hosts.yml` on Linux/macOS, `%APPDATA%\GitHub CLI\hosts.yml` on Windows)

#### Option A: GitHub CLI (recommended)

Install the GitHub CLI (`gh`), then run `gh auth login` and follow the interactive prompts.

**Windows:**

```
winget install GitHub.cli
```

Or download the installer from [cli.github.com](https://cli.github.com/).

**macOS (Homebrew):**

```bash
brew install gh
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt install gh
```

For other Linux distributions, see the [official install instructions](https://github.com/cli/cli/blob/trunk/docs/install_linux.md).

After installing, open a terminal and run:

```
gh auth login
```

Follow the browser-based login flow. Once complete, the plugin will find your token automatically.

#### Option B: personal access token (environment variable)

If you prefer not to install the GitHub CLI:

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Give it a name (e.g. "KiCad Library Manager") and check the **repo** scope
4. Click **Generate token** and copy it
5. Set it as an environment variable:
   - **Windows**: search "Environment Variables" in the Start menu → User variables → New → Name: `GITHUB_TOKEN`, Value: your token
   - **Linux / macOS**: add `export GITHUB_TOKEN="ghp_your_token_here"` to your `~/.bashrc` or `~/.zshrc`
6. Restart KiCad (it needs to pick up the new environment variable)

---

### 5) ODBC driver setup (required for KiCad DBL, not for the plugin UI)

KiCad's DBL uses an ODBC driver to read `Database/parts.sqlite`. Your DBL connection string expects the driver name:

- `SQLite3 ODBC Driver`

You can verify the registered driver list with:

```bash
odbcinst -q -d
```

#### Windows

Install the 64-bit SQLite ODBC driver:

- Download and run `sqliteodbc_w64.exe` from the upstream SQLite ODBC Driver page:  
  `http://www.ch-werner.de/sqliteodbc/`

After installing, the "SQLite3 ODBC Driver" name is typically available for ODBC connection strings.

#### Linux (Debian/Ubuntu)

Run:

```bash
sudo ./scripts/setup_odbc_linux.sh
```

This installs `unixodbc` + `libsqliteodbc` and registers the driver in `/etc/odbcinst.ini` under the name
`SQLite3 ODBC Driver`.

#### macOS (Homebrew)

Run:

```bash
./scripts/setup_odbc_macos.sh
```

This installs the Homebrew `sqliteodbc` formula (which depends on `unixodbc`) and registers the driver name
`SQLite3 ODBC Driver` in the unixODBC configuration. See Homebrew:

- `sqliteodbc`: `https://formulae.brew.sh/formula/sqliteodbc`
- `unixodbc`: `https://formulae.brew.sh/formula/unixodbc`

---

### Status colors (icons)

- **Green**: up to date / clean
- **Yellow**: local changes or newly submitted requests not yet confirmed
- **Blue**: remote applied your request; sync needed
- **Red**: remote out-of-date vs your local
- **Gray**: unknown/stale (needs Fetch remote)
