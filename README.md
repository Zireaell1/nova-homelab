# nova-homelab

[![OS: Fedora Server](https://img.shields.io/badge/OS-Fedora_Server-294172?logo=fedora&logoColor=white)](https://fedoraproject.org/server/)
[![Engine: Podman](https://img.shields.io/badge/Engine-Podman-892CA0?logo=podman&logoColor=white)](https://podman.io/)
[![Automation: Ansible](https://img.shields.io/badge/Automation-Ansible-EE0000?logo=ansible&logoColor=white)](https://docs.ansible.com/)

<p align="center">
  <img src="docs/assets/nova-rack.jpg" width="350" alt="Nova Server Rack">
</p>

> [!WARNING]
> **Work in progress**
> This project is currently under heavy development. I decided to make the repository public early so I can continue building, troubleshooting, and documenting in the open. You might find a few placeholders in the docs or Ansible roles that are still being refined, but new updates are being pushed regularly!

Hi. This is the repository for my homelab server, Nova. It serves as a home for my Ansible scripts, but also provides documentation for everything related to the server, its installation, and the build process.

Of course, this is specifically tailored for my own use case, but feel free to use it and make changes! I think there is a lot of really useful knowledge here if you are building your own server.

Keep reading below if you want to know more about the hardware, the services I'm running, and the headaches I ran into along the way. :)

> [!NOTE]
> **AI Transparency Notice**
> I know this is a sensitive topic for developers right now. I started this project as a beginner to self-hosting, so I used AI as a tutor to learn, improve my code, and help troubleshoot bugs. That being said, I never blindly copy-pasted code. Everything generated was cross-referenced with official documentation and manually fixed whenever the AI decided to hallucinate some "AI slop." :)

## Deployed Services

Here is a complete list of the services currently managed by Ansible (primarily deployed as rootless Podman Quadlets, alongside a few native system agents).

### Dashboard
| Service | Description |
| :--- | :--- |
| **[Homepage](https://gethomepage.dev/)** | The visual command center mapping out all exposed services. |

### Security
| Service | Description |
| :--- | :--- |
| **[Caddy](https://caddyserver.com/)** | Reverse proxy handling routing and automatic SSL via Cloudflare. |
| **[Pi-hole](https://pi-hole.net/)** | Network-wide ad-blocking and local DNS resolution. |
| **[Authelia](https://www.authelia.com/)** | 2FA gatekeeper for exposed services. |
| **[Tailscale](https://tailscale.com/)** | Mesh VPN installed natively on the host for secure remote access without port forwarding. |

### Smart Home & CCTV
| Service | Description |
| :--- | :--- |
| **[Home Assistant](https://www.home-assistant.io/)** | The core automation hub (running as a native container without Supervisor). |
| **[Frigate](https://frigate.video/)** | AI-powered NVR using a built-in NPU. |
| **[Zigbee2MQTT](https://www.zigbee2mqtt.io/)** | Translates physical Zigbee network traffic into MQTT. |
| **[Mosquitto](https://mosquitto.org/)** | Local MQTT broker. |

### Observability
| Service | Description |
| :--- | :--- |
| **[Grafana](https://grafana.com/)** | Main visualization UI for all server metrics and logs. |
| **[Prometheus](https://prometheus.io/)** | Time-series database scraping and storing hardware/container metrics. |
| **[Loki](https://grafana.com/oss/loki/)** | Log aggregation system for storing system and container logs. |
| **[Grafana Alloy](https://grafana.com/oss/alloy-opentelemetry-collector/)** | Native host agent routing metrics and systemd journals into the stack. |

### Backups
| Service | Description |
| :--- | :--- |
| **[Restic REST Server](https://github.com/restic/rest-server/)** | Podman container acting as a fast, secure backup target for my other devices. |
| **Custom Cloud Backups** | Custom Ansible role deploying rootless `.sh` scripts to automatically back up server data to the cloud. |

### Utilities & Hardware
| Service | Description |
| :--- | :--- |
| **[Vaultwarden](https://github.com/dani-garcia/vaultwarden/)** | Self-hosted password manager (lightweight Bitwarden alternative). |
| **[NUT](https://networkupstools.org/)** | Network UPS Tools daemon running natively on the host to monitor the physical battery backup. |
| **[Peanut](https://github.com/Brandawg93/PeaNUT/)** | Web dashboard acting as a frontend UI for the native NUT service. |
| **[OpenRGB](https://openrgb.org/)** | Hardware lighting control, built locally via a custom Podman `Containerfile`. |

## Repository Structure
Currently, the repository is split into two main areas:
* **`ansible/`** - The actual playbooks, inventory, and roles.
* **`docs/`** - The documentation. This is where I explain the services, the problems I faced, and the different choices I made.

## Docs
If you want to see exactly how this was built, check out the docs:
1. [The Hardware & 3D Printing](docs/01-hardware-and-rack.md)
2. [OS & Installation](docs/02-os-and-installation.md)
3. [Ansible](docs/03-ansible.md)
4. [Podman](docs/04-podman.md)
5. [Services Intro](docs/05-services-intro.md)
6. [Security Services](docs/06-security-services.md)
7. [Smart Home and CCTV Services](docs/07-smart-home-cctv-services.md)
