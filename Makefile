EXTENSION_UUID = velma-dictate@billbert.co
EXT_DIR = $(HOME)/.local/share/gnome-shell/extensions/$(EXTENSION_UUID)

.PHONY: help test install-daemon install-extension enable-extension disable-extension pack clean

help:
	@echo "Targets:"
	@echo "  test               Run Python test suite"
	@echo "  install-daemon     Install Python package in editable mode"
	@echo "  install-extension  Compile schemas and link extension to local GNOME Shell directory"
	@echo "  enable-extension   Enable the GNOME Shell extension"
	@echo "  disable-extension  Disable the GNOME Shell extension"
	@echo "  pack               Build .shell-extension.zip for extensions.gnome.org (EGO)"
	@echo "  clean              Remove build artifacts"

test:
	PYTHONPATH=. pytest -v

install-daemon:
	pip install -e .
	systemctl --user daemon-reload

compile-schemas:
	glib-compile-schemas extension/schemas/

install-extension: pack
	gnome-extensions install --force $(EXTENSION_UUID).shell-extension.zip
	rm -f $(EXTENSION_UUID).shell-extension.zip
	@echo "Extension installed and registered with GNOME Shell."
	@echo "Run 'make enable-extension' to activate it in the top bar."

enable-extension:
	gnome-extensions enable $(EXTENSION_UUID)

disable-extension:
	gnome-extensions disable $(EXTENSION_UUID)

pack: compile-schemas
	gnome-extensions pack extension --force --out-dir=.
	@echo "Created $(EXTENSION_UUID).shell-extension.zip ready for extensions.gnome.org"

clean:
	rm -f *.zip extension/schemas/gschemas.compiled
	find . -type d -name "__pycache__" -exec rm -rf {} +
