# Cryptoticker

A small crypto price and weather ticker for a 480×320 touchscreen, built with
[pygame](https://www.pygame.org/). Cycles through live Bitcoin, Ethereum, and
Monero prices and a 5-day weather forecast, with tap/swipe navigation between
slides.

![Cryptoticker Bitcoin slide](docs/screenshot.png)

## Features

- Live price, 24h change, and a 24h sparkline chart for BTC, ETH, and XMR
  (Binance and Kraken — no API key needed)
- Current conditions and a 5-day forecast via [Open-Meteo](https://open-meteo.com/)
  (also keyless), with hand-drawn weather icons instead of a fetched icon set
- Tap the left/right third of the screen or swipe to change slides; auto-rotates
  every 30 seconds
- No API keys or secrets required to run at all

## Requirements

- Python 3.9+
- A display — this was built for a 480×320 fullscreen touchscreen on a
  Raspberry Pi, but it'll run windowed on any desktop for testing
- `libcairo2` (native library, not a pip package) for rendering the coin logos

## Setup

```bash
git clone <this-repo> cryptoticker
cd cryptoticker
pip install -r requirements.txt
sudo apt-get install -y libcairo2   # coin logos need this; skip on non-Linux if unavailable
python3 crypto_ticker.py
```

(This repo is private — clone over SSH with a [deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys), or over HTTPS with a personal access token as the password.)

## Configuration

The weather slide needs a location, set via a local `.env` file (not
committed — copy the template and fill in your own):

```bash
cp .env.example .env
```

```
WEATHER_LABEL=Your City
WEATHER_LATITUDE=0.0000
WEATHER_LONGITUDE=0.0000
```

| Env var             | Description                          |
|----------------------|---------------------------------------|
| `WEATHER_LABEL`      | Display name on the weather slide     |
| `WEATHER_LATITUDE`   | Latitude for the Open-Meteo forecast  |
| `WEATHER_LONGITUDE`  | Longitude for the Open-Meteo forecast |

Without a `.env`, the weather slide still runs but points at `0, 0`. Everything
else (prices, charts) needs no configuration at all.

**Finding coordinates for a location** — Open-Meteo runs its own free,
keyless geocoding API, so no separate service/key is needed:

```bash
curl "https://geocoding-api.open-meteo.com/v1/search?name=Prague&count=3"
```

That returns candidate matches (there can be more than one place with the same
name) with `latitude`/`longitude` fields to copy into `.env`. Any map that
shows coordinates on click works too — e.g. right-click a spot on
[OpenStreetMap](https://www.openstreetmap.org/) or Google Maps and copy the
lat/long pair it shows.

## Running as a service (systemd)

`start_ticker.sh` isn't tracked in this repo since it hardcodes a device-specific
path — create it yourself alongside `crypto_ticker.py`:

```bash
#!/bin/bash
sleep 15
echo "$(date) Starting crypto_ticker.py" >> /tmp/cryptoticker_start.log
/usr/bin/python3 /path/to/cryptoticker/crypto_ticker.py >> /tmp/cryptoticker.log 2>&1
echo "$(date) crypto_ticker.py exited with code $?" >> /tmp/cryptoticker_start.log
```

```bash
chmod +x start_ticker.sh
```

Then a systemd unit at `/etc/systemd/system/crypto-ticker.service`:

```ini
[Unit]
Description=Crypto Ticker Display
After=graphical.target network.target
Wants=graphical.target

[Service]
User=<your-user>
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/<your-user>/.Xauthority
WorkingDirectory=/path/to/cryptoticker
ExecStart=/path/to/cryptoticker/start_ticker.sh
Restart=always

[Install]
WantedBy=default.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now crypto-ticker.service
```
