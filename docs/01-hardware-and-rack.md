# The Hardware & 3D Printing

Every homelab goes through a few iterations before you finally build something that *just works*. The setup described below is definitely not my first attempt.

My previous versions used off-the-shelf, store-bought cases, which honestly didn't give me the flexibility I needed for custom hardware. To solve that, I decided to just buy a 3D printer and make exactly what I wanted.

## The Hardware Evolution

Finding the right server hardware was a process of trial and error. I started out running a **Raspberry Pi 5 (8GB)**, then migrated to a **Beelink EQ14 mini PC** (which ended up having PSU issues and was frankly a bit faulty). Ultimately, I landed on building a custom mITX server.

I know a lot of people in the homelab community recommend buying cheap, used enterprise PCs because it's more reasonable for the price. Why did I choose the custom mITX path instead? Honestly... I just don't know! :)

### Current Hardware Specs
* **Motherboard:** [ASRock Z890I Nova WiFi](https://pg.asrock.com/mb/Intel/Z890I%20Nova%20WiFi/index.asp)
> **Fun Fact:** The server was actually named "Nova" from the very beginning, long before I even knew this motherboard existed! It wasn't planned at all—just a complete accident that the ITX board happened to share the name.
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

**Work in progress**
