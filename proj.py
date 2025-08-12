#!/usr/bin/env python3
import os, sys, subprocess, shutil

def real(p):
    """
    This function takes a path `p` and returns its absolute and canonical form.
    `os.path.realpath` is used to resolve any symbolic links in the path,
    ensuring that the script always works with the true directory location.
    This prevents ambiguity if projects are linked from different locations.
    """
    return os.path.realpath(p)

def main():
    # --- Section 1: Determine the Search Root ---
    # The script needs a single top-level directory to start its search from.
    # The primary method is to detect the root of a git repository, as this is
    # a common structure for managing multiple projects.
    git_root = None
    try:
        # First, check if the current directory is within a git work tree.
        # This avoids printing errors from `git` if run outside a repository.
        is_git_repo = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, capture_output=True, text=True).stdout.strip() == "true"
        if is_git_repo:
            # If it is a git repo, get the absolute path to its top-level directory.
            git_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8", "ignore").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # This block catches errors if `git` is not installed or if the commands fail,
        # allowing the script to proceed without relying on git.
        git_root = None

    # The `MONOREPO_ROOT` environment variable serves as a manual override.
    # If it's set, its value is used; otherwise, the detected `git_root` is used.
    root = os.environ.get("MONOREPO_ROOT", git_root)
    if not root:
        # If no root can be determined, the script cannot proceed.
        print("Not in a git repository and MONOREPO_ROOT not set.", file=sys.stderr)
        sys.exit(1)
    root = real(root) # Ensure the final root path is canonical.

    # --- Section 2: Define Project Markers ---
    # "Markers" are specific filenames that indicate the presence of a project.
    # For example, a `package.json` file marks the root of a Node.js project.
    # The default list covers many common project types. This list can be
    # overridden with the `PROJECT_MARKERS` environment variable.
    markers = os.environ.get(
        "PROJECT_MARKERS",
        "package.json go.mod pyproject.toml Cargo.toml BUILD.bazel pom.xml setup.cfg",
    ).split()

    # --- Section 3: Gather All Files for Searching ---
    # To find the markers, we first need a list of all files within the root.
    files = []
    try:
        # The preferred method is `git ls-files`, which is very fast and automatically
        # respects the project's `.gitignore` rules.
        # `-c` includes cached (tracked) files, `-o` includes other (untracked) files.
        # `--exclude-standard` applies standard git ignore rules.
        # `-z` separates filenames with a null character, handling special characters safely.
        out = subprocess.check_output(
            ["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"],
            stderr=subprocess.DEVNULL, # Hide errors if not in a git repo.
        )
        files = [f for f in out.decode("utf-8", "ignore").split("\x00") if f]
    except subprocess.CalledProcessError:
        # If `git` fails, a fallback mechanism walks the entire directory tree.
        # This method is slower and does not respect `.gitignore`.
        for d, dirs, fnames in os.walk(root):
            if ".git" in dirs:
                dirs.remove(".git") # Manually skip the .git directory.
            for f in fnames:
                files.append(os.path.relpath(os.path.join(d, f), root))

    # --- Section 4: Identify Project Directories ---
    # Iterate through the file list to find directories that contain a marker file.
    marker_set = set(markers) # Use a set for efficient O(1) lookup.
    candidates = set() # Use a set to store found project paths, automatically handling duplicates.
    for rel in files:
        base = os.path.basename(rel)
        if base in marker_set:
            # If a file is a marker, its containing directory is a project candidate.
            project_dir = os.path.dirname(rel)
            # Store the full, canonical path of the project directory.
            full = real(os.path.join(root, project_dir))
            candidates.add(full)

    # Sort the list of candidates alphabetically for a consistent and predictable order.
    candidates = sorted(candidates)
    if not candidates:
        sys.exit(1) # Exit if no projects were found.

    # --- Section 5: Prepare Data for and Interact with fzf ---
    # The list of candidates is formatted as Tab-Separated Values (TSV) for fzf.
    # This makes the data easy for fzf to parse.
    # Column 1: The project path relative to the root, for display.
    # Column 2: The full, absolute path, for use after selection.
    lines = []
    for full in candidates:
        short = os.path.relpath(full, root) or "." # Use "." for the root project itself.
        lines.append(f"{short}\t{full}")

    # Locate the fzf executable, allowing for a custom path via `FZF_BIN`.
    fzf = shutil.which(os.environ.get("FZF_BIN", "fzf")) or "fzf"
    cmd = [
        fzf, "--height=40%", "--reverse", "--border",
        "--prompt", "project> ",
        # Configure fzf to parse the TSV input.
        "--delimiter", "\t", "--with-nth", "1", # Display only the first column (relative path).
        # Generate a file listing as a preview for the highlighted directory.
        # `{2q}` is an fzf placeholder for the quoted second column (absolute path).
        "--preview", "ls -1 -- {2q} 2>/dev/null | head -100",
        # This option tells fzf to listen for specific keys and report which was pressed.
        # It enables the "open in editor" feature on Tab.
        "--expect", "tab,enter",
    ]

    # The script pipes the list of projects to fzf's standard input.
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    # `communicate` sends the data and waits for fzf to exit.
    out, _ = proc.communicate("\n".join(lines))
    if proc.returncode != 0 or not out:
        # A non-zero return code means the user exited fzf (e.g., with Esc).
        # In this case, the script should also exit cleanly.
        sys.exit(1)

    # --- Section 6: Process fzf's Output ---
    # The output from fzf when using `--expect` is a multi-line string.
    # The first line is the key that was pressed (e.g., 'tab' or 'enter').
    # The second line is the full TSV line that was selected by the user.
    parts = out.splitlines()
    if len(parts) < 2:
        sys.exit(1)

    key = parts[0].strip()
    sel = parts[1]
    if "\t" not in sel:
        sys.exit(1) # Exit if the selection format is incorrect.
    # Extract the second column (the full absolute path) from the selected TSV line.
    full = sel.split("\t", 1)[1]

    # The script's primary purpose is to output this path.
    # A shell wrapper function will capture this string from standard output
    # and use it as the destination for the `cd` command.
    print(full)

    # This is an optional enhancement. If the user pressed Tab and the `code`
    # command-line tool is available, open the selected directory in VS Code.
    if key == "tab" and shutil.which("code"):
        # `Popen` starts VS Code as a separate, detached process.
        # This allows the main script to exit immediately without waiting for the editor.
        # stdout and stderr are suppressed to not interfere with the primary output.
        subprocess.Popen(["code", full], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    main()
