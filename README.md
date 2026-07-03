# nova-homelab

> [!WARNING]
> **Work in progress**

Hi. This is the repository for my homelab server, Nova. It serves as a home for my Ansible scripts, but also provides documentation for everything related to the server, its installation, and the build process.

Of course, this is specifically tailored for my own use case, but feel free to use it and make changes! I think there is a lot of really useful knowledge here if you are building your own server.

Keep reading below if you want to know more about the hardware, the services I'm running, and the headaches I ran into along the way. :)

> [!WARNING]
> **AI Transparency Notice**
> I know this is a sensitive topic for developers right now. I started this project as a beginner to self-hosting, so I used AI as a tutor to learn, improve my code, and help troubleshoot bugs. That being said, I never blindly copy-pasted code. Everything generated was cross-referenced with official documentation and manually fixed whenever the AI decided to hallucinate some "AI slop." :)

---

## Network Architecture Diagram

**Work in progress**

---

## Repository Structure
Currently, the repository is split into three main areas:
* **`ansible/`** - The actual playbooks, inventory, and roles.
* **`3d-prints/`** - *(Work in progress)*
* **`docs/`** - The documentation. This is where I explain the services, the problems I faced, and the different choices I made.

---

## Docs
If you want to see exactly how this was built, check out the docs:
1. [The Hardware & 3D Printing](docs/01-hardware-and-rack.md)
2. [OS & Installation](docs/02-os-and-installation.md)
3. [Ansible](docs/03-ansible.md)
4. [Services](docs/04-services.md)
