[Unit]
Description=
Documentation=

Wants=network-online.target
After=network-online.target

RequiresMountsFor=

[Container]
# --- Image / Exec ---
Image=
ContainerName=
StopTimeout=120

# --- Identity / Namespaces ---
UserNS=

# --- Security / Capabilities ---
DropCapability=all
NoNewPrivileges=true

# --- Resource Limits ---
Memory=

# --- Devices ---

# --- Storage ---
Volume=

# --- Networking ---
Network=

# --- Configuration / Env ---
Timezone=

[Service]
Restart=always
RestartSec=10
TimeoutStartSec=900
TimeoutStopSec=130

[Install]
WantedBy=default.target
