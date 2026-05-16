# Air-gapped (offline) install

Install `dv-agentic-system` on a machine **without outbound internet access** using a **bundle** that already contains the project source, `scripts/`, and a **`dv_wheels/`** directory of Python wheels.

## Prerequisites

- **Python**: must satisfy the `requires-python` value in **`pyproject.toml`** at the **project root** of your bundle or clone (that file at the revision you install is the source of truth for the minimum version).
- **Shell**: use the Bash scripts under **`scripts/`** relative to that same root. Run them from a Unix-like environment (Linux, macOS, WSL, Git Bash, or similar) unless your team documents an alternate path.

## Bundle layout

After extracting an offline bundle you should be at the **project root**: a directory that contains **`pyproject.toml`**, **`dv_wheels/`**, and **`scripts/`**. The offline installer validates this layout; read **`scripts/offline-install.sh`** in your tree for the exact checks and error messages.

---

## Step 1 — Obtain a bundle

Use **one** of the options below to obtain a **`.tar.gz`** bundle, then transfer it to the air-gapped host by your site policy (USB, artifact store, etc.).

### Option A — Download a release offline asset

On [GitHub Releases](https://github.com/anlit75/dv-agentic-system/releases), download the **offline** tarball for the release and Python minor version you need. \
Transfer that **`.tar.gz`** to the air-gapped host, then continue with [**Step 2**](#step-2-install-on-the-air-gapped-host).

### Option B — Build `dv-agentic-system.tar.gz` from a clone

From any directory where you want the clone:

```bash
git clone https://github.com/anlit75/dv-agentic-system.git
cd dv-agentic-system
./scripts/offline-download.sh
```

(Optional second paste) add extra wheels that your revision’s script supports, for example:

```bash
./scripts/offline-download.sh --with-cocotb --with-dev
```

You should now have **`dv-agentic-system.tar.gz`** in the repository root. \
Transfer that file to the air-gapped host, then continue with [**Step 2**](#step-2-install-on-the-air-gapped-host).

---

## Step 2 — Install on the air-gapped host

On the **offline** machine run:

```bash
tar -xzf "/path/to/your-offline-bundle.tar.gz"
cd dv-agentic-system
./scripts/offline-install.sh
```

When the script finishes, activate **`.venv`** using the command it prints (paths differ between Windows-style and Unix-style venv layouts).

---

## What `offline-install.sh` does

In summary (authoritative behavior is the script):

1. Creates **`.venv`** with the detected `python3` or `python`.
2. Upgrades **`pip`**, **`setuptools`**, and **`wheel`** from **`dv_wheels/`** only (`--no-index`).
3. Installs the project and its dependencies from **`dv_wheels/`** with `pip install --no-index --find-links=dv_wheels .`.
4. If `import dv_agentic` succeeds, runs **`python -m dv_agentic.cli.install_agents`** to lay down agent prompt bundles expected by supported tools.

## Verify

With the venv activated:

```bash
dv-agentic --help
```

If the command is not found, confirm the venv is active and that the install step completed without errors.
