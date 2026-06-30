# The Hardware & 3D Printing

Every homelab goes through a few iterations before you finally build something that *just works*. The setup described below is definitely not my first attempt.

My previous versions used off-the-shelf, store-bought cases, which honestly didn't give me the flexibility I needed for custom hardware. To solve that, I decided to just buy a 3D printer and make exactly what I wanted.

## The Hardware Evolution

Finding the right server hardware was a process of trial and error. I started out running a **Raspberry Pi 5 (8GB)**, then migrated to a **Beelink EQ14 mini PC** (which ended up having PSU issues and was frankly a bit faulty). Ultimately, I landed on building a custom mITX server.

I know a lot of people in the homelab community recommend buying cheap, used enterprise PCs because it's more reasonable for the price. Why did I choose the custom mITX path instead? Honestly... I just don't know! :)

### Current Hardware Specs
* **Motherboard:** [ASRock Z890I Nova WiFi](https://pg.asrock.com/mb/Intel/Z890I%20Nova%20WiFi/index.asp)
> **Fun Fact:** The server was actually named "Nova" from the very beginning, long before I even knew this motherboard existed! It wasn't planned at all—just a completely accident that the ITX board happened to share the name.
* **CPU:** Intel Core Ultra 5 225
* **RAM:**
* **Storage:**
* **Power Supply:**

## The Rack & 3D Printing

For the rack itself, I am using a **DeskPi T2**. It’s a pretty tall setup at **12U**, and outside of the power strips, literally every case and mount sitting in it is 3D printed.

### Printer & Filament Choices
Everything was printed on my **Creality K1 Max**.

For the materials, I used **Fiberlogy** filaments in a two-tone color scheme:
* **PETG Matte Red**
* **PETG-CF Black**

> [!WARNING]
> I highly recommend *against* using PLA for server racks. The ambient temperatures around the server itself can get quite warm, and with PLA, there is always a very real risk of warping over time. PETG handles the heat perfectly.

### Community Models & Custom Modifications
I didn't design every piece from scratch. For almost all of the bays, I used existing models from the amazing communities over at Printables.com and Makerworld.com.

However, to make the rack look clean and professional, I imported these models into **Blender** before printing them. I adjusted them to ensure they all shared common, standardized front-plate dimensions:
* **Width:** `254.24mm`
* **Thickness:** `5mm`
* **Height:** 1U = `44.45mm`

I also modified the screw holes so that every single 1U plate perfectly uses two screws on each side.

Because I heavily rely on and respect the work of the original creators, here is exactly what I used and where you can find the original files:

### 3D Printed Parts List
| Component | Modification Details | Original Source Link |
| :--- | :--- | :--- |

**Work in progress**
