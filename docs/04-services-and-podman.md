# Services & Podman

Before diving into the specific services, we need to talk about the engine that runs them. If you look through the repository, you won't find a single `docker-compose.yml` file. As mentioned in previous chapters, we don't use Docker. We use **Podman**—specifically, we run every container using **Podman Quadlets** natively integrated with `systemd`.

So why choose Podman over Docker? Let's be honest: Docker is definitely the easier setup. Almost every self-hosted service provides a handy `docker-compose` file in their documentation. It's basically copy, paste, run a single command, and it just works. Previous iterations of this server ran on Docker, and it was totally fine. However, I kept seeing Podman highly recommended online, and since I was building this new version on Fedora, I decided it was the perfect time to experiment.

What are the actual advantages of Podman?
1. **Daemonless & Rootless:** Unlike Docker, Podman doesn't require a background daemon running as root. Every service on this server runs securely under a standard, unprivileged user account.
2. **Native Systemd Integration:** This is the killer feature. Podman Quadlets allow you to define containers using standard `.container` files that the OS (`systemd`) understands natively.

*(Yes, you can configure Docker to run rootless or Podman to run rootful. But the general consensus is: if you want rootless, use Podman. If you want rootful, stick with Docker).*

### The Cons (The Struggles)

So, what are the downsides of Podman? Fighting to build those `.container` files is definitely the main one.

Because we are running them rootless and as systemd services, you often have to manually translate the official Docker Compose files into Quadlet syntax. Sometimes you even have to dig into a project's raw `Dockerfile` just to see what internal user it expects. You *will* fight with permissions, specifically hardware device access (**I hate you, Frigate**—it's running, but still not perfect!) and advanced networking quirks (**I hate you too, Pi-hole**—preserving original client IP addresses for DNS queries is a notoriously difficult task).

**How do rootless permissions actually work?**
Essentially, the container inherits the exact permissions of the host user running the service. If your standard Linux user has access to a hardware device (like a Coral TPU or a GPU), the container will have access to it. If the user doesn't, the container doesn't either.

---

### How the Ansible Roles Work

Going back to the repository structure, if you look inside any service role's `templates/` directory, you will usually find three files:
* `xyz.container.j2` — The systemd definition for the service.
* `xyz.network.j2` — Defines the isolated Podman network for the service.
* `xyz.env.j2` — Contains environment variables the service needs.

*(They all have the `.j2` suffix because they are Jinja2 templates).*

The `.container` file is the core file, and it directly references the `.network` and `.env` files.

When you run the Ansible playbook, it isn't magically executing `podman run` commands in the background. It is simply taking those Jinja2 templates, generating the final files, dropping them directly into `~/.config/containers/systemd/`, and telling `systemd` to start it up.

This means containers act exactly like native OS services. They auto-start on boot, perfectly respect dependency startup orders, and pump all of their logs directly into standard Linux `journalctl`.
