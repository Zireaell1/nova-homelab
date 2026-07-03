# Ansible

The core of this entire repository is the Ansible automation. Since we already set up our SSH keys in the previous chapter, running Ansible against the server should be a breeze.

Before we run anything, let's look at what is actually in here. The whole repo is built around **Ansible Roles**. In a perfect, enterprise-grade world, these roles should be completely independent from each other. However, because these were built specifically for *this exact homelab*, I didn't pay too much attention to making them perfectly modular. Sorry about that!

### The Directory Structure
If you look inside the `ansible/` directory, here is how everything is organized:

* **`group_vars/`** — Contains the variables shared across multiple roles.
  * `all/services.yaml`: Shared configurations specific to the deployed services.
  * `all/vars.yaml`: General shared variables for the server.
  * `all/versions.yaml`: The master version list. If you want to update a specific container/service version, this is the exact file you change.
* **`ansible-ci.cfg`** — The configuration file used by GitHub Actions for automatic Ansible Linting when code is pushed to `main`.
* **`ansible.cfg`** — The local configuration used when executing Ansible against the server.
* **`requirements.yml`** — Defines external Ansible Galaxy collections required to make this work. You will likely need to install these locally first.
* **`playbook.yml`** — The master playbook that executes the roles against the server.
* **`update.yml`** — A specialized playbook used solely for updating the host OS software (not the containers, just the base system).

Inside the `roles/` directory, each individual service has its own folder. They generally follow this structure:
* **`defaults/`**: Variables specific only to that role.
* **`handlers/`**: Triggers that fire at the end of a playbook run (e.g., "Restart service XYZ if a config changed").
* **`tasks/`**: The main sequence of steps Ansible will execute to deploy the service.
* **`files/`**: Just static files, nothing more. :)
* **`templates/`**: Similar to files, but these use Jinja2 templating so Ansible can inject variables into them dynamically.

---

## Setting up Ansible Vault (Secrets)

Now, enough explanation—how do we actually run this?

First, we need to handle secrets. Most of these services require passwords, API tokens, or database credentials to run. For obvious security reasons, I don't push these to the public repository. Instead, I use Ansible Vault.

I have provided an example file at `examples/vault.yml.example`. To create your own encrypted vault, navigate to your `ansible/` directory and run:

```bash
ansible-vault create group_vars/all/vault.yml
```

It will prompt you to create a vault password. (Remember this password—the file is heavily encrypted and will need to be decrypted during every playbook execution). Once your terminal editor opens, paste the contents of the `.example` file, fill in all of your actual secret values, save, and exit.

> [!TIP]
> If you ever need to change a password later, you can edit the encrypted file using:
> `ansible-vault edit group_vars/all/vault.yml`

**Quality of Life Fix:** Typing the vault password every single time you run a playbook gets annoying fast. You can create a file named `.vault_pass` inside the `ansible/` directory and write your password inside it as plain text. Ansible will read this file automatically. *(Just make absolutely sure this file stays in your `.gitignore`!)*

---

## Setting up the Inventory

The next step is telling Ansible where to find your server. There is an example inventory file located at `examples/inventory.ini`.

Create a new file at `ansible/inventory.ini`, copy the example content, and swap the values:

```ini
server_name ansible_host=server_ip ansible_user=server_user
```

* **`server_name`**: The friendly name for your server (we will use this in the command line later).
* **`ansible_host`**: The actual IP address of your server.
* **`ansible_user`**: The username you use to log in (the one we set up SSH keys for).

And that is it! The configuration is officially done.

---

## Running the Playbook

To actually deploy the services, navigate to the `ansible/` directory in your terminal and run:

```bash
ansible-playbook playbook.yml --tags "tag1,tag2" --limit "server_name"
```

* **`--tags`**: Each role inside `playbook.yml` is assigned a tag. By specifying tags here, you tell Ansible exactly which roles/services you want to deploy or update, ignoring the rest.
* **`--limit`**: This tells Ansible exactly which machine from your `inventory.ini` to run against.

### The Test Run (Dry Run)

If you are making changes and want to see what Ansible *would* do without actually breaking anything, you can run the exact same command with the `--check` flag:

```bash
ansible-playbook playbook.yml --tags "tag1,tag2" --limit "server_name" --check
```

This performs a dry run, giving you a report of what would have changed.
