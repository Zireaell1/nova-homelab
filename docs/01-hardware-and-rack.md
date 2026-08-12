# The Hardware & 3D Printing

Every homelab goes through a few iterations before you finally build something that *just works*. The setup described below is definitely not my first attempt.

My previous versions used off-the-shelf, store-bought cases, which honestly didn't give me the flexibility I needed for custom hardware. To solve that, I decided to just buy a 3D printer and make exactly what I wanted.

## The Hardware Evolution

Finding the right server hardware was a process of trial and error. I started out running a **Raspberry Pi 5 (8GB)**, then migrated to a **Beelink EQ14 mini PC** (which ended up having PSU issues and was frankly a bit faulty). Ultimately, I landed on building a custom mITX server.

I know a lot of people in the homelab community recommend buying cheap, used enterprise PCs because it's more reasonable for the price. Why did I choose the custom mITX path instead? Honestly... I just don't know! :)

### Current Server Hardware Specs
* **Motherboard:** [ASRock Z890I Nova WiFi](https://pg.asrock.com/mb/Intel/Z890I%20Nova%20WiFi/index.asp)
> **Fun Fact:** The server was actually named "Nova" from the very beginning, long before I even knew this motherboard existed! It wasn't planned at all - just a complete accident that the ITX board happened to share the name.
* **CPU:** [Intel Core Ultra 5 225](https://www.intel.com/content/www/us/en/products/sku/241070/intel-core-ultra-5-processor-225-20m-cache-up-to-4-90-ghz/specifications.html)
* **RAM:** [G.SKILL Trident Z5 RGB DDR5 2x16GB 6000MHz CL30](https://www.gskill.com/product/165/374/1649235161/F5-6000J3040F16GX2-TZ5RK-F5-6000J3040F16GA2-TZ5RK)
* **Storage:**
  * **System:** Samsung NVMe 9100 PRO 1TB
  * **Backup:** WD Blue 2TB 3.5"
  * **CCTV:** WD Purple 4TB 3.5"
* **Power Supply:** [Corsair SF750 750W](https://www.corsair.com/us/en/p/psu/cp-9020284-na/sf-series-sf750-fully-modular-80-plus-platinum-sfx-power-supply-cp-9020284-na)

## The Rack & 3D Printing

For the rack itself, I am using a **DeskPi T2**. It’s a pretty tall setup at **12U**, and outside of the power strips, literally every case and mount sitting in it is 3D printed.

| Unit | Front View | Back View |
| :---: | :--- | :--- |
| **U12** | 200mm Fan | Blank Panel (with additional case for Zigbee coordinator) |
| **U11** | Raspberry Pi & E-ink Display | Blank Panel |
| **U10** | Patch Panel | Blank Panel |
| **U9** | Network Switch | Blank Panel |
| **U8** | Blank Panel (Vented) | Blank Panel |
| **U7** | Server (2U) | Patch Panel (routes internally to front patch panel) |
| **U6** | Server (2U) | Blank Panel |
| **U5** | Two-Bay HDD Drives | Blank Panel (glued to HDD bay supports) |
| **U4** | Blank Panel | Server PSU (2U) |
| **U3** | Blank Panel (Vented) | Server PSU (2U) |
| **U2** | Blank Panel (Vented) | 4-Slot Power Strip |
| **U1** | Blank Panel (Vented) | Blank Panel |

### Printer & Filament Choices
Everything was printed on my **Creality K1 Max**.

For the materials, I used **Fiberlogy** filaments in a two-tone color scheme:
* [PETG Matte Red](https://fiberlogy.com/en/Matte-PETG-Filament-1_75mm-0_85kg#variantOptions=44:1697)
* [PETG-CF Black](https://fiberlogy.com/en_US/c/PETG-CF/147)

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
| Component | Original Source Link |
| :--- | :--- |
| Two-Bay HDD Drives | [Printables.com](https://www.printables.com/model/1290788-10-inch-rack-1u-2-x-35-inch-hdd-hot-swap) |
| Mini ITX Case | [Printables.com](https://www.printables.com/model/1403788-2u-mini-itx-case-for-10-rack-with-keystones) |
| 200mm Fan Case | [Printables.com](https://www.printables.com/model/1320430-200-mm-fan-10-inch-rack-mount) |
| Blank Panel (Vented) | [Printables.com](https://www.printables.com/model/1374300-10-server-rack-panel-1u-3p-blank) |
| SFX PSU Case | [Printables.com](https://www.printables.com/model/1333725-10-inch-rack-sfx-psu-mount) |
| Switch Case | [Printables.com](https://www.printables.com/model/1314827-tp-link-tl-sg108-tl-sg108pe-tl-sf1006p-10-inch-rac) |
| Keystone Blank Insert Pass-Through | [Printables.com](https://www.printables.com/model/1327671-keystone-blank-insert-pass-through) |

**List - Work in Progress**

## The E-Ink Display & Controller

(TODO: screen image)

As you can see in the U11 slot of the rack table, there is a **Raspberry Pi 5 (8GB)** driving a [Waveshare 2.9" e-Paper Module (V2)](https://www.waveshare.com/wiki/2.9inch_e-Paper_Module).

The first versions of the script running on it were pretty simple - just basic progress bars and numbers for CPU, RAM, and drive usage. However, I wanted to add something that would make it more interesting and visually engaging on an e-ink display (since you have to be pretty close to read small text anyway).

To make it more immersive, I added a character that reacts dynamically based on the server's metrics and the time of day. For example, it sleeps at night, listens to music during the day, and looks visibly concerned when memory usage spikes.

(TODO: reactions images)

The screen is controlled via a custom script which you can find [here](https://github.com/Zireaell1/nova-eink-display). My `eink_display` Ansible role already attempts to set this up automatically, but for now, you will need to provide your own image assets to make it work. Why? Because my specific version of the character was AI-generated, downscaled, converted to pure black and white, and then manually pixel-edited to look good on the e-ink screen. I don't want to share AI-generated content in the main repo right now, but if someone really wants my specific assets, feel free to open a GitHub Issue and I can share them!

And yes, a Raspberry Pi 5 8GB is a completely massive overkill for driving a simple e-ink display script. The only reason I used it here is because I already had it bought and sitting around unused. :)

## Power & UPS

(TODO: ups image)

Even though it isn't listed in the 12U rack table, the server is backed by a [Eaton UPS](https://www.eaton.com/pl/pl-pl/skuPage.5E900UF.html).

It sits outside the main setup. In the first iterations of the build, I tried to keep the UPS at the bottom of the rack, but it took up way too much space. To be honest, it didn't even fit properly into the DeskPi rack - it was too long and visibly stuck out the back.

Currently, the main power cable from the rack's power strip goes directly into the external UPS. I also have a 2-meter USB cable running from the UPS back to the server so my **NUT (Network UPS Tools)** service can monitor it.

With the current power draw of the server (which hovers around 100-110W most of the time), the UPS provides about **25 minutes** of battery backup. This is actually perfect, because power outages in my area generally only last for a moment. If the power stays out longer, NUT is configured to gracefully shut the server down once the UPS battery drops to around 30%.

## The HDD Bay

The HDDs are located directly under the server. I was initially concerned if fitting them there would have any impact on their temperatures. Fortunately, it seems they have a generally perfect environment down there.

They are stored in a 3D-printed bay with two slots. The author of the model actually has multiple [versions](https://www.printables.com/model/1290788-10-inch-rack-1u-2-x-35-inch-hdd-hot-swap) available. If you can solve the issue with available SATA slots (for example, by adapting the unused M.2 slot on the back of this motherboard, or just using a different board entirely), you could easily use a 2U bay with more drives. But for now, there are just two.

For the trays, I bought used enterprise server drive caddies. At the back of the 3D-printed bay, there are SATA adapters attached so you just slide the drives right into the slots. In my case, I don't use and haven't even configured the hot-swap functionality, so they are generally just for looks. Still, in case of a drive failure, it's always easier to swap them without touching any cables.

## Network Layout

The physical network setup here is relatively simple, but intentionally split. There are two distinct networks: a standard internet-facing network, and a second, physically isolated local network.

As the heart of the homelab, the server needs access to both. If you're wondering how I achieved this since the ITX motherboard only has one built-in Ethernet port - I added an additional [M.2 Ethernet adapter](https://www.amazon.pl/StarTech-com-1-portowa-sieciowa-Ethernet-Multi-Gigabit/dp/B0CV4DX2FX). It sits underneath the motherboard, so it’s completely hidden from view.

Here is how the routing works:
* **The Internet Network:** This connection is straightforward. The main cable from my router goes straight into the primary server port, giving server access to the outside world.
* **The Isolated Network:** The secondary M.2 port connects directly to the rack's [network switch](). This switch handles multiple local devices that absolutely do not need outside internet access. As long as the server can talk to them locally, that’s all that matters.

All of these devices and the server itself are routed through the custom 3D-printed front patch panel. Why? Because... it looks cool!

Honestly, if I didn't care about the "datacenter aesthetic," this could have been wired much more simply. Because of the patch panel, there are some slightly chaotic internal connections hidden in the back. For example, the cable routing from the server's Ethernet interface to the patch panel actually consists of two shorter cables joined together with an internal keystone... purely because I didn't have a single cable long enough to reach the front patch panel and then loop back to the switch! :D

## LEDs

(TODO: image / gif leds)

Now let's talk about the most important thing in the entire rack: the RGB LEDs, of course!

I used [these exact LED strips](). It took some time to find the right ones, but they ended up being perfect for this build. The kit comes with two strips for the left and right sides, and they are just long enough to cover almost the entire 12U height. They plug directly into the ARGB header on the ITX motherboard.

I managed to get them working through **OpenRGB** (which actually has its own dedicated Ansible role in this repository). Unfortunately, even though the LED strips are theoretically addressable, lighting up individual LEDs doesn't seem to work right now. I suspect the ARGB controller on the ASRock motherboard is a bit too simple to handle pixel-level control (though I need to research this a bit more). However, all of the standard lighting presets work perfectly.

OpenRGB is also connected to Home Assistant. This means the server rack lighting is fully integrated into my smart home, allowing me to build automations around it like turning the rack to a specific color during the day, and having it automatically shut the lights off at night.

## Zigbee Coordinator

At the back of the rack, up at the U12 level, I mounted a Sonoff Zigbee coordinator. This dongle is used by Zigbee2MQTT to communicate with all the Zigbee smart devices around the house. That is pretty much its entire physical job! I dive much deeper into the software side of this setup in the [Zigbee2MQTT documentation]().

For the physical connection, a USB cable runs from the coordinator at the back, routes inside the rack, comes out the front, and plugs directly into the motherboard's front panel USB slots.

I originally thought about wiring it up a bit more cleanly by connecting it directly to the internal USB headers on the motherboard. However, I couldn't find the correct interface/adapter for those pins, so I haven't tried it yet. Plus, honestly, having the USB cable routed into the front I/O actually looks really nice, so I just decided to keep it like that.

## The "Other Boring Stuff"

There are a few other miscellaneous components I needed to actually wire everything together. There honestly isn't much to explain about them, but for the sake of a fully complete parts list, here is the rest of the hardware inside the rack:

* [200mm Top Exhaust Fan]()
* [10-inch Rack Power Strip]()
* [RJ45 Keystones]()
* [Short Ethernet Patch Cables]()
* [SATA Cables]()
* [Fan Extension Cables]()
* [USB Cables]()
