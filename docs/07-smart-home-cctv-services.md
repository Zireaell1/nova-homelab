# Smart Home & CCTV Services

This next chapter is all about the smart home and the CCTV system. Because these systems rely so heavily on talking to each other locally, let's start with the glue that holds them together.

## Mosquitto

Let's start with Mosquitto because it is the foundational layer for the other services to communicate. Mosquitto is simply an MQTT broker. It doesn't have a UI, it doesn't need an internet connection, and in fact, internet access is completely blocked because it runs on an isolated, internal Podman network!

Its sole purpose is to act as a local data bus so that Zigbee2MQTT and Frigate can send their messages to Home Assistant in real-time.

---

## Zigbee2MQTT

*[Work in Progress - Zigbee2MQTT Image]*

Zigbee2MQTT (Z2M) is the service that directly translates raw Zigbee radio signals into standard MQTT text messages. It manages the physical Zigbee coordinator (the hardware that actually talks to your smart plugs, temperature sensors, etc.).

For my setup, I use the **Sonoff ZBDongle-E** connected directly to the server via USB. It works flawlessly, but to get the best stability, you usually need to flash its firmware. In my case, I currently use version `8.2.2` from `[repo link]`, and I can confirm it is highly stable.

### Flashing the Dongle
If you ever need to flash the software, you don't need to install a bunch of random tools. The `zigbee2mqtt` Ansible role already sets up a Python virtual environment specifically for this, pre-loaded with [universal-silabs-flasher](https://github.com/NabuCasa/universal-silabs-flasher).

To flash the dongle, first find out what your connected coordinator is named in the OS (usually `/dev/ttyACM0` or `/dev/ttyUSB0`), activate the virtual environment, and run the flasher:

```bash
# Activate the Ansible-created python venv
source /path/to/venv/bin/activate

# Run the flasher tool
universal-silabs-flasher \
    --device /dev/ttyUSB0 \
    --bootloader-reset rts_dtr \
    flash \
    --firmware firmware_file_name.gbl
```

*(Make sure to change the `--device` and `--firmware` flags to match your actual setup).*

It should take about a minute to complete. Once done, you have a solid coordinator ready to pair with Z2M. From there, Z2M simply grabs the data from all your physical devices and pushes it straight to Mosquitto, making it instantly available in Home Assistant.

---

## Home Assistant

*[Work in Progress - Home Assistant Image]*

## Frigate

*[Work in Progress - Frigate Image]*
