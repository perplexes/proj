# Project Navigator (`proj`)

## What is this?

`proj` is a command-line utility designed to rapidly find and switch between different project directories within a monorepo or any organized collection of projects. It uses `fzf` to provide a fast and intuitive interactive fuzzy-search interface.

## Why use it?

In large codebases, especially monorepos, navigating between dozens or even hundreds of individual projects can be slow and cumbersome. Standard `cd` commands require you to remember and type out long, nested paths. This tool solves that problem by creating a dynamic menu of all identified projects, allowing you to jump to your destination in just a few keystrokes.

The core philosophy is to make directory navigation context-aware and frictionless, saving developer time and reducing cognitive load.

## How it Works

The script operates in a few key stages:

1.  **Root Detection**: It first identifies the root of your monorepo. It defaults to using the top-level directory of the current `git` repository, but this can be overridden with a `MONOREPO_ROOT` environment variable.

2.  **Project Discovery**: It searches the entire file tree under the root for project "marker" files. These are files like `package.json`, `go.mod`, or `pyproject.toml` that signify the root of a distinct project. The list of markers is configurable.

3.  **Interactive Selection**: The list of discovered projects is piped into `fzf`, which displays an interactive search prompt. As you type, `fzf` filters the list in real-time.

4.  **Directory Switching**: Once you select a project, the script prints its absolute path to standard output. A simple shell wrapper (see below) can then use this output to `cd` into the selected directory.

5.  **Editor Integration (Optional)**: If you press `Tab` instead of `Enter` on a selection, the script will also attempt to open the selected project directory in Visual Studio Code.

## Installation and Usage

### Prerequisites

-   [fzf](https://github.com/junegunn/fzf): The command-line fuzzy finder.
-   `python3`
-   (Optional) `git`: For automatic root detection in git repositories.
-   (Optional) `code`: The VS Code command-line tool, for editor integration.

### Setup

1.  Place the `proj.py` script somewhere in your `PATH`.
2.  Add the following wrapper function to your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`):

    ```sh
    proj() {
        local dest
        dest=$(python3 /path/to/your/proj.py)
        if [[ -n "$dest" ]]; then
            cd "$dest"
        fi
    }
    ```

    *Remember to replace `/path/to/your/proj.py` with the actual path to the script.*

3.  Reload your shell configuration (`source ~/.zshrc`) or open a new terminal.

### Customization

You can control the script's behavior with environment variables:

-   `MONOREPO_ROOT`: Set an absolute path to your projects' root directory. This overrides the `git` root-finding logic.
-   `PROJECT_MARKERS`: A space-separated string of filenames to use for project discovery.
    -   Example: `export PROJECT_MARKERS="package.json pom.xml"`
-   `FZF_BIN`: Specify the path to the `fzf` executable if it's not in your `PATH`.
