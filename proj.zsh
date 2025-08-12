proj() {
  local dest
  dest="$(proj.py)" || return
  [[ -n "$dest" && -d "$dest" ]] && builtin cd -- "$dest"
}
