Hi! Thank you for your interest in contributing to my homelab. The guidelines here are intentionally simple.

While this repository is tailored to my personal infrastructure, I am always open to more elegant ways of doing things, bug fixes, and general improvements!

## How to Contribute

* **For major changes or new features:** Please open an **Issue** or **Discussion** first. This lets us agree on the approach before you spend your valuable time writing code.
* **For simple changes or bug fixes:** Feel free to open a **Pull Request** directly. Just include a brief explanation of what you changed and why.

## Linting and Standards

This repository has an automated GitHub Actions workflow configured to run **Ansible Lint**. Your code will need to pass this check.

> [!TIP]
> If you use Visual Studio Code, I highly recommend installing the [official Ansible extension](https://marketplace.visualstudio.com/items?itemName=redhat.ansible). It catches most linting errors and formatting issues directly in the editor as you type.

## Handling Secrets (Ansible Vault)

**Never commit unencrypted secrets or real Ansible Vault files to this repository.**

If your PR requires adding new secure variables:
1. Add the variable names with dummy data to the example vault file: `examples/vault.yml.example`.
2. Explain what the new variables do and how they should be configured in your PR description.
3. Keep your actual vault files strictly local.
