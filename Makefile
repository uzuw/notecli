PREFIX ?= $(HOME)/.local
PYTHON ?= python3

.PHONY: install uninstall test check link

install: link
	@echo "installed: $(PREFIX)/bin/note -> $(CURDIR)/note"

link:
	@mkdir -p $(PREFIX)/bin
	@ln -sf $(CURDIR)/note $(PREFIX)/bin/note

uninstall:
	@rm -f $(PREFIX)/bin/note
	@echo "removed $(PREFIX)/bin/note (notes and index left in ~/.local/share/note)"

test:
	$(PYTHON) -m pytest tests/ -q

check:
	$(PYTHON) -m py_compile note
	@echo "note compiles cleanly"
