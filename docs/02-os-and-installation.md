# OS & Installation

Before we get to the fun stuff (like the services), we need to set up the OS.

If you browse homelab forums, you will mostly read about virtualizing with Proxmox, or sticking to the tried-and-true Debian with Docker. Because I like to experiment and wanted a more cutting-edge OS, I chose... **Fedora!** (The headless Server Edition, of course). To be honest, it has been running beautifully from day one. I even managed a major version upgrade from Fedora 43 to 44 without a single hiccup.

Fedora also pairs perfectly with Podman. My previous server iterations used Docker, but since I was jumping into Fedora, I figured - why not try Podman? The only real learning curve was **SELinux**. Sometimes it complains when a container wants to access a specific hardware device or requires elevated permissions. Troubleshooting exactly what SELinux wants can definitely be a headache at times!

Of course, this doesn't mean Fedora is the definitive "best" choice. I can't speak much to Proxmox since I haven't used it, and Debian is undeniably the more reliable, set-it-and-forget-it choice. It comes down to a tradeoff: older, rock-solid software vs. managing more frequent updates for recent features. For me, the cutting-edge features won.

> [!WARNING]
> **A quick heads-up:** The Ansible tasks written in this repository are specifically tailored for Fedora Server. I cannot guarantee that all of them will work out-of-the-box on other operating systems (like Debian or Ubuntu). Still, you are welcome to use them as a baseline and adapt them for your own setup!

### The LVM Mistake

When I originally installed Fedora, I messed up the partitioning and didn't set up `/home` as a separate LVM (Logical Volume) right away. I had to improvise and set it up manually via the command line later, which was a huge pain and is obviously not covered by the Ansible automation.

Let me save you the headache: **do it directly in the Fedora GUI installer!** It is by far the easiest way to handle it. Note that my Ansible scripts (**hardware** role) *assume* `/home` is already set up as its own LVM volume, so do not skip this.

## The Installation Config

You can configure the installation however you want, but for future reference (and as a set of "dumb install instructions" for myself), here is exactly how Nova should be configured in the installer:
- **Partitioning:** Custom (Ensure `/home` is created as a separate LVM volume)
- **Software Selection:** Do not install additional software (Minimal)
- **Root Account:** Disabled
- **Mirrors:** Install from the closest mirror
- **Language/Keyboard:** ENG language with PL + EN keyboard layouts
- **Networking:** Default settings

I don't have any screenshots of the installer, so for now, this simple note will have to do! :)

## After Installation

The very first thing that should be done on a fresh install is a simple system update:

```bash
sudo dnf upgrade --refresh
```

Let it install the updates, give the server a quick `sudo reboot`, and the base OS is done.

## Setup SSH Keys

I use macOS as my daily driver, so these instructions are slightly tailored to Apple's ecosystem (specifically the keychain stuff). If you are on Linux or Windows, the process is almost identical - just skip the Apple-specific flags.

First, generate a new modern SSH key. I highly recommend using `ed25519`:

```bash
ssh-keygen -t ed25519 -C "nova-server-key"
```

*Hit enter to accept the default file location, and make sure to set a secure passphrase!*

Next, add the key to the macOS SSH agent so it saves to your keychain. This saves you from typing the passphrase every single time:

```bash
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

Now, copy your public key over to the Fedora server:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub server_username@server_ip
```

### The Quality of Life Fix (macOS)

If you don't want to manually load the key or type your passphrase every time you reboot your Mac, you need to tell SSH to always use the keychain. Create or edit your `~/.ssh/config` file:

```text
Host *
  UseKeychain yes
  AddKeysToAgent yes
  IdentityFile ~/.ssh/id_ed25519
```

*(Note: If your terminal ever forgets the key and asks for a passphrase anyway, running `ssh-add --apple-load-keychain` will manually load it for your current session.)*

### The Test

Finally, let's make sure it actually works. Try to SSH into the server:

```bash
ssh server_username@server_ip
```

If you instantly drop into the Fedora terminal without it asking for a password, you are golden!
