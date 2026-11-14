SHELL := /bin/sh
.DEFAULT_GOAL := help
ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
export PATH := $(HOME)/.local/bin:$(HOME)/.cargo/bin:$(PATH)
.NOTPARALLEL:

.PHONY: help system system-update install update rust cargo uv tools plugins link shell check
help:
	@/usr/bin/python3 "$(ROOT)scripts/setup.py" help
system:
	@/usr/bin/python3 "$(ROOT)scripts/system.py"
system-update: system
install:
	@$(MAKE) --no-print-directory -C "$(ROOT)" rust uv tools link plugins check
update:
	@/usr/bin/python3 "$(ROOT)scripts/setup.py" update
cargo: rust
rust uv tools plugins link shell check:
	@/usr/bin/python3 "$(ROOT)scripts/setup.py" "$@"
