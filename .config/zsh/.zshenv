# Keep noninteractive SSH commands quiet; no aliases or optional scripts here.
typeset -U path
path=("$HOME/.local/bin" "$HOME/bin" "$HOME/.cargo/bin" $path)
export EDITOR=nvim
export VISUAL=nvim
