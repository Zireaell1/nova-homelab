# Ansible

The core of this entire repository is the Ansible automation. Since we already set up our SSH keys in the previous chapter, running Ansible against the server should be a breeze.

Before we run anything, let's look at what is actually in here. The whole repo is built around **Ansible Roles**. In a perfect, enterprise-grade world, these roles should be completely independent from each other. However, because these were built specifically for *this exact homelab*, I didn't pay too much attention to making them perfectly modular. Sorry about that!

### The Directory Structure
If you look inside the `ansible/` directory, here is how everything is organized:

* **`group_vars/`** - Contains the variables shared across multiple roles.
  * `all/services.yaml`: Shared configurations specific to the deployed services.
  * `all/vars.yaml`: General shared variables for the server.
* **`ansible-ci.cfg`** - The configuration file used by GitHub Actions for automatic Ansible Linting when code is pushed to `main`.
* **`ansible.cfg`** - The local configuration used when executing Ansible against the server.
* **`requirements.yml`** - Defines external Ansible Galaxy collections required to make this work. You will likely need to install these locally first.
* **`site.yml`** - The master playbook that executes basically everything.
* **`playbooks/`** - The directory containing all the individual, split playbooks.

Inside the `roles/` directory, each individual service has its own folder. They generally follow this structure:
* **`defaults/`**: Variables specific only to that role.
* **`handlers/`**: Triggers that fire at the end of a playbook run (e.g., "Restart service XYZ if a config changed").
* **`tasks/`**: The main sequence of steps Ansible will execute to deploy the service.
* **`files/`**: Just static files, nothing more. :)
* **`templates/`**: Similar to files, but these use Jinja2 templating so Ansible can inject variables into them dynamically.

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

There are also currently two additional playbooks used for the maintenance of the main Nova server:

**Work in progress**

## Setting up Ansible Vault (Secrets)

Now, enough explanation - how do we actually run this?

First, we need to handle secrets. Most of these services require passwords, API tokens, or database credentials to run. For obvious security reasons, I don't push these to the public repository. Instead, I use Ansible Vault.

I have provided an example file at `examples/vault.yml.example`. To create your own encrypted vault, navigate to your `ansible/` directory and run:

```bash
ansible-vault create group_vars/all/vault.yml
```

It will prompt you to create a vault password. (Remember this password - the file is heavily encrypted and will need to be decrypted during every playbook execution). Once your terminal editor opens, paste the contents of the `.example` file, fill in all of your actual secret values, save, and exit.

> [!TIP]
> If you ever need to change a password later, you can edit the encrypted file using:
> `ansible-vault edit group_vars/all/vault.yml`

**Quality of Life Fix:** Typing the vault password every single time you run a playbook gets annoying fast. You can create a file named `.vault_pass` inside the `ansible/` directory and write your password inside it as plain text. Ansible will read this file automatically. *(Just make absolutely sure this file stays in your `.gitignore`!)*

## Setting up the Inventory

The next step is telling Ansible where to find your server. There is an example inventory file located at `examples/inventory.ini`.

Create a new file at `ansible/inventory.ini`, copy the example content, and swap the values:

```ini
server_name ansible_host=server_ip ansible_user=server_user
```

* **`server_name`**: The friendly name for your server (e.g., `nova` or `orion`).
* **`ansible_host`**: The actual IP address of your server.
* **`ansible_user`**: The username you use to log in (the one we set up SSH keys for).

And that is it! The configuration is officially done.

## Running the Playbook

To actually deploy the services, navigate to the `ansible/` directory in your terminal and run:

```bash
# Example 1: Running a root-level system playbook (requires -K for sudo)
ansible-playbook playbooks/nova_system.yml -K

# Example 2: Running a rootless services playbook
ansible-playbook playbooks/nova_services.yml
```

If you only want to deploy or update a single specific service instead of running the entire playbook, you can use the `--tags` flag. Each role inside the playbooks is assigned a tag (usually matching the service name).

```bash
# Example 3: Updating just Grafana and Prometheus
ansible-playbook playbooks/nova_services.yml --tags "grafana,prometheus"
```

### The Test Run (Dry Run)

If you are making changes and want to see what Ansible *would* do without actually breaking anything, you can run the exact same command with the `--check` flag:

```bash
ansible-playbook playbooks/nova_services.yml --tags "grafana" --check
```

This performs a dry run, giving you a report of what would have changed.
