# Raspberry Pi Wi-Fi setup

Wi-Fi credentials belong in the Raspberry Pi operating system, not in this dashboard app or git repo.

## Raspberry Pi OS with desktop

Use the network icon or Raspberry Pi Imager advanced settings.

## Headless Raspberry Pi OS / NetworkManager

On newer Raspberry Pi OS releases:

```bash
sudo nmcli dev wifi list
sudo nmcli dev wifi connect "YOUR_WIFI_NAME" password "YOUR_WIFI_PASSWORD"
```

## wpa_supplicant-style systems

Older Raspberry Pi OS images may use `/etc/wpa_supplicant/wpa_supplicant.conf`:

```bash
sudo wpa_passphrase "YOUR_WIFI_NAME" "YOUR_WIFI_PASSWORD" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf
sudo wpa_cli -i wlan0 reconfigure
```

## Verify connectivity

```bash
ip addr show wlan0
ping -c 3 8.8.8.8
curl -I https://api.openweathermap.org
```

Do not paste real Wi-Fi passwords into Discord/chat. Type them directly on the Raspberry Pi or use Raspberry Pi Imager's local setup options.
