# Ansible

The core of this entire repository is the Ansible automation. Since we already set up our SSH keys in the previous chapter, running Ansible against the server should be a breeze.

Before we run anything, let's look at what is actually in here. The whole repo is built around **Ansible Roles**. In a perfect, enterprise-grade world, these roles should be completely independent from each other. However, because these were built specifically for *this exact homelab*, I didn't pay too much attention to making them perfectly modular. Sorry about that!

### The Directory Structure
If you look inside the `ansible/` directory, here is how everything is organized:

* **`group_vars/all/`** - Contains the variables shared across multiple roles.
  * `vars.yml`: General shared variables (timezone, hostnames, small shared settings).
  * `paths.yml`: Every directory path the roles use.
  * `podman.yml`: The Podman networks and rootless settings.
  * `endpoints.yml`: The registry of services and their subdomains.
  * `backup.yml`: What gets backed up, and which services are stopped for it.
* **`host_vars/`** - Facts about one specific machine (disk UUIDs, network interface names, USB device paths).
* **`ansible.cfg`** - The configuration used when executing Ansible against the server (and by CI).
* **`Makefile`** - Short commands for running the playbooks (`make nova_services t=grafana`) and the checks.
* **`requirements.yml`** - Defines external Ansible Galaxy collections required to make this work. `make deps` installs them.
* **`site.yml`** - The master playbook that executes basically everything.
* **`playbooks/`** - The directory containing all the individual, split playbooks.

The Python tooling itself (ansible-core, ansible-lint, yamllint) is pinned in `pyproject.toml` / `uv.lock` at the repository root and managed with [uv](https://docs.astral.sh/uv/).

Inside the `roles/` directory, each individual service has its own folder. They generally follow this structure:
* **`defaults/`**: Variables specific only to that role.
* **`handlers/`**: Triggers that fire at the end of a playbook run (e.g., "Restart service XYZ if a config changed").
* **`tasks/`**: The main sequence of steps Ansible will execute to deploy the service.
* **`files/`**: Just static files, nothing more. :)
* **`templates/`**: Similar to files, but these use Jinja2 templating so Ansible can inject variables into them dynamically.
* **`meta/`**: Where a role has `argument_specs.yml`, the list of variables it accepts. Ansible checks them before the role runs.

Most container roles do not deploy anything themselves: they hand a short list of directories, templates and quadlets to the shared **`podman_service`** role, which does the deployment and decides when to restart.

## Ansible Playbooks

Let's talk a bit more about the playbooks themselves. Currently, we have two physical machines defined: **Nova** (the main server) and **Orion** (the Raspberry Pi that controls the e-ink screen).

Both of them have two separate playbooks:
1. **System Playbooks:** These set up the foundation, configure the OS, install native software, and generally require root (`sudo`) permissions.
2. **Services Playbooks:** These add configuration files at the user level, set up Podman services, and run scripts - all completely rootless.

I designed it this way so it is completely transparent what permissions each playbook needs and what it can do. From a security standpoint, the rootless ones are significantly safer to run and update.

If you ever call the system-level playbooks directly, remember that they need the `-K` parameter so Ansible can ask for the root password.

Here are the core files inside the `playbooks/` directory:
* `nova_system.yml` - Needs root (`-K`)
* `nova_services.yml` - Rootless
* `orion_system.yml` - Needs root (`-K`)
* `orion_services.yml` - Rootless

There are also two additional playbooks used for the maintenance of the main Nova server:
* `nova_update_check.yml` - Lists the available DNF updates without installing anything. Needs root (`-K`)
* `nova_update.yml` - Installs all updates and reports whether a reboot is needed. Needs root (`-K`)

## Setting up Ansible Vault (Secrets)

Now, enough explanation - how do we actually run this?

First, we need to handle secrets. Most of these services require passwords, API tokens, or database credentials to run. For obvious security reasons, I don't push these to the public repository. Instead, I use Ansible Vault.

I have provided an example file at `examples/vault.yml.example`. To create your own encrypted vault, navigate to your `ansible/` directory and run:

```bash
uv run ansible-vault create group_vars/all/vault.yml
```

It will prompt you to create a vault password. (Remember this password - the file is heavily encrypted and will need to be decrypted during every playbook execution). Once your terminal editor opens, paste the contents of the `.example` file, fill in all of your actual secret values, save, and exit.

> [!TIP]
> If you ever need to change a password later, you can edit the encrypted file using:
> `uv run ansible-vault edit group_vars/all/vault.yml`

**Quality of Life Fix:** Typing the vault password every single time you run a playbook gets annoying fast. You can create a file named `.vault_pass` inside the `ansible/` directory and write your password inside it as plain text. `ansible.cfg` points at this file, so Ansible reads it automatically - and will refuse to start if it is missing. *(It is already in `.gitignore`; make absolutely sure it stays there!)*

## Setting up the Inventory

The next step is telling Ansible where to find your server. There is an example inventory file located at `examples/inventory.ini.example`.

Create a new file at `ansible/inventory.ini`, copy the example content, and swap the values:

```ini
server_name ansible_host=server_ip ansible_user=server_user
```

* **`server_name`**: The name of your server. It must be `nova` or `orion` - the playbooks target the machines by these names.
* **`ansible_host`**: The actual IP address of your server.
* **`ansible_user`**: The username you use to log in (the one we set up SSH keys for).

And that is it! The configuration is officially done.

## Running the Playbook

To actually deploy the services, navigate to the `ansible/` directory in your terminal and run:

```bash
# Example 1: Running a root-level system playbook (the Makefile adds -K for sudo)
make nova_system

# Example 2: Running a rootless services playbook
make nova_services
```

If you only want to deploy or update a single specific service instead of running the entire playbook, pass tags with `t=`. Each role inside the playbooks is assigned a tag (usually matching the service name).

```bash
# Example 3: Updating just Grafana and Prometheus
make nova_services t=grafana,prometheus
```

`make help` lists every target. Under the hood these are plain `uv run ansible-playbook playbooks/<name>.yml` calls with `--tags`, `--check` and `-K` added as needed.

### The Test Run (Dry Run)

If you are making changes and want to see what Ansible *would* do without actually breaking anything, add `c=1` (Ansible's `--check`):

```bash
make nova_services t=grafana c=1
```

This performs a dry run, giving you a report of what would have changed.
