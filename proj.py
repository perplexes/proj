#!/usr/bin/env python3
import os, sys, subprocess, shutil

def real(p): return os.path.realpath(p)

def main():
    # Root + markers (customize via env)
    git_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8", "ignore").strip()
    root = real(os.environ.get("MONOREPO_ROOT", git_root))
    markers = os.environ.get(
        "PROJECT_MARKERS",
        "package.json go.mod pyproject.toml Cargo.toml BUILD.bazel pom.xml setup.cfg",
    ).split()

    # Gather files respecting .gitignore (tracked + unignored untracked)
    files = []
    try:
        out = subprocess.check_output(
            ["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"],
            stderr=subprocess.DEVNULL,
        )
        files = [f for f in out.decode("utf-8", "ignore").split("\x00") if f]
    except subprocess.CalledProcessError:
        # Fallback: walk filesystem, skip .git
        for d, dirs, fnames in os.walk(root):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in fnames:
                files.append(os.path.relpath(os.path.join(d, f), root))

    marker_set = set(markers)
    candidates = set()

    for rel in files:
        base = os.path.basename(rel)
        if base in marker_set:
            full = real(os.path.join(root, os.path.dirname(rel)))
            candidates.add(full)

    candidates = sorted(candidates)
    if not candidates:
        sys.exit(1)

    # Build TSV for fzf: "<short>\t<full>"
    lines = []
    for full in candidates:
        short = os.path.relpath(full, root)
        if short == ".":
            short = "."
        lines.append(f"{short}\t{full}")

    fzf = shutil.which(os.environ.get("FZF_BIN", "fzf")) or "fzf"
    cmd = [
        fzf, "--height=40%", "--reverse", "--border",
        "--prompt", "project> ",
        "--delimiter", "\t", "--with-nth", "1",
        "--preview", "ls -1 -- {2q} 2>/dev/null | head -100",
        "--expect", "tab,enter",
    ]

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    out, _ = proc.communicate("\n".join(lines))
    if proc.returncode != 0 or not out:
        sys.exit(1)

    parts = out.splitlines()
    if len(parts) < 2:
        sys.exit(1)

    key = parts[0].strip()
    sel = parts[1]
    # field 2 is absolute path
    if "\t" not in sel:
        sys.exit(1)
    full = sel.split("\t", 1)[1]

    # Print the destination so the shell wrapper can `cd` to it.
    print(full)

    # Optional: on Tab, also open in VS Code (does not affect stdout)
    if key == "tab" and shutil.which("code"):
        subprocess.Popen(["code", full], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    main()
