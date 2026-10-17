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

# --- EXTRA VARS (e.g., e=podman_service_changed_extra=true) ---
ifdef e
  EXTRA_FLAG := -e "$(e)"
endif

# --- RESTORE (targets=a,b snapshot=<id> repo=local|b2 list=1) ---
RESTORE_VARS := $(if $(targets),-e restore_targets=$(targets)) $(if $(snapshot),-e restore_snapshot=$(snapshot)) \
	$(if $(repo),-e restore_repo=$(repo)) $(if $(list),-e restore_list=true)

# --- BASE COMMAND ---
CMD = uv run ansible-playbook $(TAG_FLAG) $(CHECK_FLAG) $(BECOME_FLAG) $(EXTRA_FLAG)

# --- PLAYBOOK LISTS ---
ROOT_PLAYBOOKS := site
DIR_PLAYBOOKS := nova_system nova_services orion_system orion_services nova_update nova_update_check orion_update

.PHONY: help deps lint check restore_nova $(ROOT_PLAYBOOKS) $(DIR_PLAYBOOKS)

help:
	@echo "Usage:"
	@echo "  make <playbook> [t=tag] [c=1] [k=1]"
	@echo ""
	@echo "Setup and checks:"
	@echo "  make deps                (sync .venv from uv.lock, install collections into .collections)"
	@echo "  make lint                (ansible-lint + yamllint)"
	@echo "  make check               (structural checks from scripts/ci, same as CI)"
	@echo ""
	@echo "Playbooks (root directory):"
	@echo "  make site                (Auto -K; all four plays, for a rebuild or a full idempotency check)"
	@echo ""
	@echo "Playbooks (playbooks/ directory):"
	@echo "  make nova_system         (Auto -K)"
	@echo "  make orion_system        (Auto -K)"
	@echo "  make nova_update         (Auto -K)"
	@echo "  make nova_update_check   (Auto -K)"
	@echo "  make orion_update        (Auto -K)"
	@echo "  make nova_services"
	@echo "  make orion_services"
	@echo ""
	@echo "Examples:"
	@echo "  make nova_services c=1                                             (dry-run all tasks)"
	@echo "  make nova_system t=dotfiles c=1                                    (dry-run only 'dotfiles' tag)"
	@echo "  make nova_services k=1                                             (force -K on services)"
	@echo "  make lint check                                                    (everything CI runs, locally)"
	@echo "  make nova_services t=grafana e=podman_service_changed_extra=true   (force a restart)"
	@echo ""
	@echo "Restore:"
	@echo "  make restore_nova [targets=..] [snapshot=<id>] [repo=b2] [list=1]  (Auto -K; -> /mnt/backup/restore/<time> on Nova)"

# --- SETUP ---
deps:
	uv sync --locked
	uv run ansible-galaxy collection install -r requirements.yml

# --- CHECKS ---
lint:
	uv run ansible-lint
	uv run yamllint -c .yamllint -s . ../.github/
	shellcheck roles/*/files/*.sh

check:
	uv run python ../scripts/ci/run.py

# --- TARGET-SPECIFIC VARIABLES ---
site nova_system orion_system nova_update nova_update_check orion_update restore_nova: BECOME_FLAG = -K

# --- RUN RULES ---
$(ROOT_PLAYBOOKS):
	$(CMD) $@.yml

$(DIR_PLAYBOOKS):
	$(CMD) playbooks/$@.yml

restore_nova:
	$(CMD) playbooks/$@.yml $(RESTORE_VARS)
