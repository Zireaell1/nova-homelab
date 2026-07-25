# --- TAGS (e.g., t=caddy) ---
ifdef t
  TAG_FLAG := --tags "$(t)"
endif

# --- DRY-RUN (e.g., c=1) ---
ifdef c
  CHECK_FLAG := --check
endif

# --- MANUAL BECOME (-K) (e.g., k=1) ---
ifdef k
  BECOME_FLAG := -K
endif

# --- BASE COMMAND ---
CMD = ansible-playbook $(TAG_FLAG) $(CHECK_FLAG) $(BECOME_FLAG)

# --- PLAYBOOK LISTS ---
ROOT_PLAYBOOKS := site
DIR_PLAYBOOKS := nova_system nova_services orion_system orion_services nova_update nova_update_check

.PHONY: help $(ROOT_PLAYBOOKS) $(DIR_PLAYBOOKS)

help:
	@echo "Usage:"
	@echo "  make <playbook> [t=tag] [c=1] [k=1]"
	@echo ""
	@echo "Playbooks (root directory):"
	@echo "  make site"
	@echo ""
	@echo "Playbooks (playbooks/ directory):"
	@echo "  make nova_system         (Auto -K)"
	@echo "  make orion_system        (Auto -K)"
	@echo "  make nova_update         (Auto -K)"
	@echo "  make nova_update_check   (Auto -K)"
	@echo "  make nova_services"
	@echo "  make orion_services"
	@echo ""
	@echo "Examples:"
	@echo "  make nova_services c=1              (dry-run all tasks)"
	@echo "  make nova_system t=dotfiles c=1     (dry-run only 'dotfiles' tag)"
	@echo "  make nova_services k=1              (force -K on services)"

# --- TARGET-SPECIFIC VARIABLES ---
nova_system orion_system nova_update nova_update_check: BECOME_FLAG = -K

# --- RUN RULES ---
$(ROOT_PLAYBOOKS):
	$(CMD) $@.yml

$(DIR_PLAYBOOKS):
	$(CMD) playbooks/$@.yml
