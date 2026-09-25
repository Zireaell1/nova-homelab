[Unit]
Description=
Documentation=

RequiresMountsFor=

[Container]
# --- Image / Exec ---
Image=
ContainerName=
StopTimeout=20

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

EnvironmentFile=

# --- Healthcheck ---
HealthCmd=
HealthInterval=60s
HealthTimeout=10s
HealthRetries=3
HealthStartPeriod=60s

[Service]
Restart=always
RestartSec=10
TimeoutStartSec=900
TimeoutStopSec=30

[Install]
WantedBy=default.target
