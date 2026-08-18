# -*- coding: utf-8 -*-
import os
import math
import time
import datetime
from io import BytesIO

import numpy as np
import requests
import cairosvg
from dotenv import load_dotenv
from PIL import Image, ImageDraw

import pygame
import pygame.gfxdraw

load_dotenv()

pygame.init()

SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

PAD_X = 22
HEADER_TOP = 18
DOTS_BOTTOM_MARGIN = 12

ARROW_SHOW_TIME = 1.0  # seconds the arrow stays visible

# ---------------------------------------------------------------------------
# Palette (validated for contrast + colorblind separation with the dataviz
# palette checker: node validate_palette.js "#c98a2e,#3aa873,#e5665a" --mode dark)
# ---------------------------------------------------------------------------
BG = (18, 21, 28)
CARD = (27, 32, 41)
CARD_BORDER = (46, 52, 64)
TEXT_PRIMARY = (238, 240, 244)
TEXT_MUTED = (131, 139, 160)
TEXT_FAINT = (86, 94, 112)
ACCENT = (201, 138, 46)
GREEN = (58, 168, 115)
RED = (229, 102, 90)
RAIN_BLUE = (91, 143, 189)


def blend(bg, fg, alpha):
    return tuple(int(bg[i] * (1 - alpha) + fg[i] * alpha) for i in range(3))


GREEN_SOFT = blend(BG, GREEN, 0.18)
RED_SOFT = blend(BG, RED, 0.18)
GRIDLINE = blend(CARD, (255, 255, 255), 0.07)

FONT_PATH = "JetBrainsMono-SemiBold.ttf"
font_price = pygame.font.Font(FONT_PATH, 38)
font_change = pygame.font.Font(FONT_PATH, 16)
font_label = pygame.font.Font(FONT_PATH, 15)
font_small = pygame.font.Font(FONT_PATH, 12)
font_wx_temp = pygame.font.Font(FONT_PATH, 34)
font_forecast_temp = pygame.font.Font(FONT_PATH, 19)
font_arrow = pygame.font.Font(FONT_PATH, 50)

# All coins available to pick from. 'source' picks which exchange serves both
# the price and the chart, so a coin never straddles two APIs for one slide.
COIN_REGISTRY = {
    'bitcoin': {
        'source': 'binance',
        'symbol': 'BTCUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/btc.svg',
        'tint': (247, 147, 26),
    },
    'ethereum': {
        'source': 'binance',
        'symbol': 'ETHUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/refs/heads/master/svg/color/eth.svg',
        'tint': (98, 126, 234),
    },
    'monero': {
        'source': 'kraken',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/refs/heads/master/svg/color/xmr.svg',
        'tint': (255, 140, 40),
    },
    'solana': {
        'source': 'binance',
        'symbol': 'SOLUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/sol.svg',
        'tint': (153, 69, 255),
    },
    'cardano': {
        'source': 'binance',
        'symbol': 'ADAUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/ada.svg',
        'tint': (0, 51, 173),
    },
    'dogecoin': {
        'source': 'binance',
        'symbol': 'DOGEUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/doge.svg',
        'tint': (194, 159, 63),
    },
    'litecoin': {
        'source': 'binance',
        'symbol': 'LTCUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/ltc.svg',
        'tint': (52, 131, 193),
    },
    'ripple': {
        'source': 'binance',
        'symbol': 'XRPUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/xrp.svg',
        'tint': (90, 100, 120),
    },
    'polkadot': {
        'source': 'binance',
        'symbol': 'DOTUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/dot.svg',
        'tint': (230, 0, 122),
    },
    'chainlink': {
        'source': 'binance',
        'symbol': 'LINKUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/link.svg',
        'tint': (42, 91, 237),
    },
    'binancecoin': {
        'source': 'binance',
        'symbol': 'BNBUSDT',
        'logo_url': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/svg/color/bnb.svg',
        'tint': (240, 185, 11),
    },
}

DEFAULT_CRYPTO_COINS = ['bitcoin', 'ethereum', 'monero']

# CRYPTO_COINS picks which coins show up and in what order, e.g.
# "bitcoin,solana,dogecoin" - see .env.example / README for the full list.
_requested_coins = [
    c.strip().lower()
    for c in os.environ.get('CRYPTO_COINS', '').split(',')
    if c.strip()
] or DEFAULT_CRYPTO_COINS

COINS = {}
for _key in _requested_coins:
    if _key in COIN_REGISTRY:
        COINS[_key] = COIN_REGISTRY[_key]
    else:
        print(f"Unknown coin '{_key}' in CRYPTO_COINS, skipping. "
              f"Available: {', '.join(COIN_REGISTRY)}")

if not COINS:
    COINS = {k: COIN_REGISTRY[k] for k in DEFAULT_CRYPTO_COINS}

# Set via WEATHER_LABEL / WEATHER_LATITUDE / WEATHER_LONGITUDE in a local
# .env file (see .env.example) - deliberately no real-location default here.
WEATHER = {
    'label': os.environ.get('WEATHER_LABEL', 'Set WEATHER_LABEL'),
    'latitude': float(os.environ.get('WEATHER_LATITUDE', '0.0')),
    'longitude': float(os.environ.get('WEATHER_LONGITUDE', '0.0')),
}

SLIDE_NAMES = list(COINS.keys()) + ['weather']

PRICE_CACHE_TTL = 20        # seconds
CHART_CACHE_TTL = 5 * 60    # seconds
WEATHER_CACHE_TTL = 10 * 60  # seconds

price_cache = {}
chart_cache = {}
weather_cache = {}
logo_cache = {}


def get_cached(cache, key, ttl, fetch_fn, is_valid=lambda v: v is not None):
    """Fetch-with-TTL-cache that falls back to the last good value on error."""
    now = time.time()
    entry = cache.get(key)
    if entry is not None and now - entry[1] < ttl:
        return entry[0]
    value = fetch_fn()
    if is_valid(value):
        cache[key] = (value, now)
        return value
    return entry[0] if entry is not None else value


# ---------------------------------------------------------------------------
# Small drawing helpers
# ---------------------------------------------------------------------------

def render_tracked(font, text, color, tracking=2):
    """Render text with extra letter-spacing (pygame fonts have none built in)."""
    glyphs = [font.render(ch, True, color) for ch in text]
    width = sum(g.get_width() for g in glyphs) + tracking * max(0, len(glyphs) - 1)
    height = font.get_height()
    surf = pygame.Surface((max(width, 1), height), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        surf.blit(g, (x, (height - g.get_height()) // 2))
        x += g.get_width() + tracking
    return surf


def draw_rounded_panel(surface, rect, fill, border=None, radius=14, border_width=1):
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


def fmt_price(value):
    if value >= 100:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def draw_filled_circle(surface, x, y, r, color):
    x, y, r = int(x), int(y), max(1, int(r))
    pygame.gfxdraw.filled_circle(surface, x, y, r, color)
    pygame.gfxdraw.aacircle(surface, x, y, r, color)


# ---------------------------------------------------------------------------
# Weather icons, hand-drawn so the slide never depends on an external icon CDN
# ---------------------------------------------------------------------------

def draw_cloud_shape(surface, cx, cy, w, color):
    h = w * 0.62
    r = h * 0.5
    draw_filled_circle(surface, cx - w * 0.22, cy - h * 0.08, r * 0.78, color)
    draw_filled_circle(surface, cx + w * 0.12, cy - h * 0.22, r * 0.62, color)
    draw_filled_circle(surface, cx + w * 0.30, cy + h * 0.02, r * 0.50, color)
    base = pygame.Rect(int(cx - w * 0.42), int(cy - h * 0.02), int(w * 0.84), int(h * 0.42))
    pygame.draw.rect(surface, color, base, border_radius=int(h * 0.2))


def draw_sun(surface, cx, cy, r, color, rays=True):
    draw_filled_circle(surface, cx, cy, r, color)
    if not rays:
        return
    ray_len = r * 0.55
    gap = r * 0.35
    width = max(2, int(r * 0.16))
    for i in range(8):
        ang = i * (math.pi / 4)
        x1 = cx + math.cos(ang) * (r + gap)
        y1 = cy + math.sin(ang) * (r + gap)
        x2 = cx + math.cos(ang) * (r + gap + ray_len)
        y2 = cy + math.sin(ang) * (r + gap + ray_len)
        pygame.draw.line(surface, color, (x1, y1), (x2, y2), width)


def draw_rain(surface, cx, top_y, w, color, drops=3):
    spacing = w / (drops + 1)
    width = max(2, int(w * 0.05))
    for i in range(drops):
        x = cx - w / 2 + spacing * (i + 1)
        pygame.draw.line(surface, color, (x, top_y), (x - w * 0.07, top_y + w * 0.24), width)


def draw_snow(surface, cx, top_y, w, color, flakes=3):
    spacing = w / (flakes + 1)
    s = w * 0.07
    width = max(1, int(w * 0.035))
    for i in range(flakes):
        x = cx - w / 2 + spacing * (i + 1)
        y = top_y + w * 0.12
        pygame.draw.line(surface, color, (x - s, y), (x + s, y), width)
        pygame.draw.line(surface, color, (x, y - s), (x, y + s), width)
        pygame.draw.line(surface, color, (x - s * 0.7, y - s * 0.7), (x + s * 0.7, y + s * 0.7), width)
        pygame.draw.line(surface, color, (x - s * 0.7, y + s * 0.7), (x + s * 0.7, y - s * 0.7), width)


def draw_fog(surface, cx, top_y, w, color, lines=3):
    spacing = w * 0.14
    width = max(2, int(w * 0.045))
    for i in range(lines):
        y = top_y + i * spacing
        pygame.draw.line(surface, color, (cx - w * 0.32, y), (cx + w * 0.32, y), width)


def draw_lightning(surface, cx, top_y, w, color):
    pts = [
        (cx - w * 0.10, top_y),
        (cx + w * 0.18, top_y),
        (cx - w * 0.02, top_y + w * 0.34),
        (cx + w * 0.14, top_y + w * 0.34),
        (cx - w * 0.20, top_y + w * 0.78),
        (cx - w * 0.02, top_y + w * 0.40),
        (cx - w * 0.16, top_y + w * 0.40),
    ]
    pygame.draw.polygon(surface, color, pts)


def weather_icon_kind(code):
    if code == 0:
        return 'clear'
    if code in (1, 2):
        return 'partly_cloudy'
    if code == 3:
        return 'cloudy'
    if code in (45, 48):
        return 'fog'
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return 'rain'
    if code in (71, 73, 75, 77, 85, 86):
        return 'snow'
    if code in (95, 96, 99):
        return 'storm'
    return 'cloudy'


def draw_weather_icon(surface, cx, cy, size, kind):
    cloud_color = TEXT_MUTED
    if kind == 'clear':
        draw_sun(surface, cx, cy, size * 0.30, ACCENT)
    elif kind == 'partly_cloudy':
        draw_sun(surface, cx - size * 0.16, cy - size * 0.14, size * 0.20, ACCENT, rays=False)
        draw_cloud_shape(surface, cx + size * 0.06, cy + size * 0.08, size * 0.72, cloud_color)
    elif kind == 'cloudy':
        draw_cloud_shape(surface, cx, cy, size * 0.80, cloud_color)
    elif kind == 'fog':
        draw_cloud_shape(surface, cx, cy - size * 0.16, size * 0.72, cloud_color)
        draw_fog(surface, cx, cy + size * 0.22, size * 0.80, cloud_color)
    elif kind == 'rain':
        draw_cloud_shape(surface, cx, cy - size * 0.16, size * 0.76, cloud_color)
        draw_rain(surface, cx, cy + size * 0.16, size * 0.60, RAIN_BLUE)
    elif kind == 'snow':
        draw_cloud_shape(surface, cx, cy - size * 0.16, size * 0.76, cloud_color)
        draw_snow(surface, cx, cy + size * 0.22, size * 0.60, TEXT_PRIMARY)
    elif kind == 'storm':
        draw_cloud_shape(surface, cx, cy - size * 0.16, size * 0.76, cloud_color)
        draw_lightning(surface, cx, cy + size * 0.04, size * 0.36, ACCENT)


# ---------------------------------------------------------------------------
# Data fetching (cached so switching slides doesn't re-hit every API)
# ---------------------------------------------------------------------------

def load_logo_rounded(url, size=(40, 40), radius=10):
    cache_key = (url, size, radius)
    if cache_key in logo_cache:
        return logo_cache[cache_key]
    try:
        response = requests.get(url, timeout=5)
        if url.endswith('.svg'):
            png_data = cairosvg.svg2png(bytestring=response.content, output_width=size[0], output_height=size[1])
            img = Image.open(BytesIO(png_data)).convert("RGBA")
        else:
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)

        if radius > 0:
            mask = Image.new('L', img.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
            img.putalpha(mask)

        surface = pygame.image.fromstring(img.tobytes(), img.size, img.mode).convert_alpha()
        logo_cache[cache_key] = surface
        return surface
    except Exception as e:
        print(f"Error fetching logo image: {e}")
        return None


def fetch_price(coin):
    key = coin.get('symbol') or coin['source']

    def _fetch():
        try:
            if coin['source'] == 'kraken':
                url = 'https://api.kraken.com/0/public/Ticker?pair=XMRUSD'
                r = requests.get(url, timeout=5).json()
                ticker = r['result']['XXMRZUSD']
                price = float(ticker['c'][0])
                open_price = float(ticker['o'])
                change = ((price - open_price) / open_price) * 100
                return price, change
            else:
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin['symbol']}"
                r = requests.get(url, timeout=5).json()
                price = float(r['lastPrice'])
                change = float(r['priceChangePercent'])
                return price, change
        except Exception as e:
            print(f"Error fetching price for {key}: {e}")
            return None, 0

    return get_cached(price_cache, key, PRICE_CACHE_TTL, _fetch, is_valid=lambda v: v[0] is not None)


def fetch_chart_data(coin):
    key = coin.get('symbol') or coin['source']

    def _fetch():
        try:
            if coin['source'] == 'kraken':
                url = 'https://api.kraken.com/0/public/OHLC?pair=XMRUSD&interval=15'
                r = requests.get(url, timeout=5).json()
                result_key = next(k for k in r['result'] if k != 'last')
                candles = r['result'][result_key][-96:]
                prices = [float(c[4]) for c in candles]
            else:
                end = int(time.time() * 1000)
                start = end - 24 * 60 * 60 * 1000
                url = f"https://api.binance.com/api/v3/klines?symbol={coin['symbol']}&interval=15m&startTime={start}&endTime={end}"
                r = requests.get(url, timeout=5).json()
                prices = [float(c[4]) for c in r]
            if not prices:
                return [], 0, 0
            return prices, min(prices), max(prices)
        except Exception as e:
            print(f"Error fetching chart data for {key}: {e}")
            return [], 0, 0

    return get_cached(chart_cache, key, CHART_CACHE_TTL, _fetch, is_valid=lambda v: bool(v[0]))


def fetch_weather():
    key = (WEATHER['latitude'], WEATHER['longitude'])

    def _fetch():
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={WEATHER['latitude']}&longitude={WEATHER['longitude']}"
                "&current=temperature_2m,weather_code"
                "&daily=weather_code,temperature_2m_max,temperature_2m_min"
                "&timezone=auto&forecast_days=6"
            )
            r = requests.get(url, timeout=5).json()
            forecasts = []
            daily = r['daily']
            for i in range(1, len(daily['time'])):
                forecasts.append({
                    'date': daily['time'][i],
                    'code': daily['weather_code'][i],
                    'max': daily['temperature_2m_max'][i],
                    'min': daily['temperature_2m_min'][i],
                })
                if len(forecasts) >= 5:
                    break
            return {
                'temp': r['current']['temperature_2m'],
                'code': r['current']['weather_code'],
                'forecasts': forecasts,
            }
        except Exception as e:
            print(f"Weather fetch error: {e}")
            return None

    return get_cached(weather_cache, key, WEATHER_CACHE_TTL, _fetch)


# ---------------------------------------------------------------------------
# Chart rendering — a small gradient-fill area chart, drawn without matplotlib
# ---------------------------------------------------------------------------

def render_area_chart(prices, width, height, color):
    if len(prices) < 2 or width <= 0 or height <= 0:
        return None, []

    lo, hi = min(prices), max(prices)
    span = (hi - lo) or 1.0
    margin = span * 0.1
    lo -= margin
    hi += margin
    span = hi - lo

    n = len(prices)
    points = [
        (i * (width - 1) / (n - 1), height - ((p - lo) / span) * height)
        for i, p in enumerate(prices)
    ]

    mask = Image.new('L', (width, height), 0)
    polygon = [(round(x), round(y)) for x, y in points] + [(width, height), (0, height)]
    ImageDraw.Draw(mask).polygon(polygon, fill=255)

    gradient_col = np.linspace(95, 0, height, dtype=np.float32).reshape(height, 1)
    gradient = np.tile(gradient_col, (1, width))
    mask_arr = np.array(mask, dtype=np.float32) / 255.0
    alpha_arr = (gradient * mask_arr).astype(np.uint8)

    fill_img = Image.new('RGBA', (width, height), color + (0,))
    fill_img.putalpha(Image.fromarray(alpha_arr, mode='L'))

    surface = pygame.image.fromstring(fill_img.tobytes(), fill_img.size, fill_img.mode).convert_alpha()
    return surface, points


# ---------------------------------------------------------------------------
# Slide chrome shared across crypto + weather slides
# ---------------------------------------------------------------------------

def render_dots(surface, index, total, y):
    dot_gap = 9
    small = 7
    pill_w = 20
    widths = [pill_w if i == index else small for i in range(total)]
    total_w = sum(widths) + dot_gap * (total - 1)
    x = (SCREEN_WIDTH - total_w) // 2
    for i, w in enumerate(widths):
        if i == index:
            rect = pygame.Rect(x, y - small // 2, w, small)
            pygame.draw.rect(surface, ACCENT, rect, border_radius=small // 2)
        else:
            draw_filled_circle(surface, x + small / 2, y, small / 2, TEXT_FAINT)
        x += w + dot_gap


def render_header(surface, logo_surface, name, tint):
    chip = pygame.Rect(PAD_X, HEADER_TOP, 40, 40)
    draw_rounded_panel(surface, chip, blend(BG, tint, 0.16), radius=10)
    if logo_surface:
        logo_rect = logo_surface.get_rect(center=chip.center)
        surface.blit(logo_surface, logo_rect)

    label = render_tracked(font_label, name.upper(), TEXT_MUTED, tracking=3)
    label_rect = label.get_rect(midleft=(chip.right + 11, chip.centery))
    surface.blit(label, label_rect)

    live_dot_r = 4
    live_text = render_tracked(font_small, "LIVE", TEXT_FAINT, tracking=2)
    live_x = SCREEN_WIDTH - PAD_X - live_text.get_width()
    live_y = chip.centery
    draw_filled_circle(surface, live_x - live_dot_r * 2 - 6, live_y, live_dot_r + 2, blend(BG, GREEN, 0.25))
    draw_filled_circle(surface, live_x - live_dot_r * 2 - 6, live_y, live_dot_r, GREEN)
    surface.blit(live_text, live_text.get_rect(midleft=(live_x, live_y)))


def render_change_pill(surface, change, top_y):
    up = change >= 0
    color = GREEN if up else RED
    soft = GREEN_SOFT if up else RED_SOFT
    text = f"{'+' if up else ''}{change:.2f}%"
    text_surf = font_change.render(text, True, color)

    tri = 7
    gap = 6
    pad_x, pad_y = 13, 6
    content_w = tri + gap + text_surf.get_width()
    pill_w = content_w + pad_x * 2
    pill_h = text_surf.get_height() + pad_y * 2
    pill_rect = pygame.Rect(0, 0, pill_w, pill_h)
    pill_rect.centerx = SCREEN_WIDTH // 2
    pill_rect.top = top_y
    draw_rounded_panel(surface, pill_rect, soft, radius=pill_h // 2)

    cx = pill_rect.left + pad_x
    cy = pill_rect.centery
    if up:
        tri_pts = [(cx, cy - tri * 0.55), (cx + tri, cy + tri * 0.45), (cx - tri, cy + tri * 0.45)]
    else:
        tri_pts = [(cx, cy + tri * 0.55), (cx + tri, cy - tri * 0.45), (cx - tri, cy - tri * 0.45)]
    pygame.gfxdraw.filled_trigon(surface, *[int(v) for p in tri_pts for v in p], color)

    surface.blit(text_surf, text_surf.get_rect(midleft=(cx + tri + gap, cy)))
    return pill_rect.bottom


def render_chart_card(surface, rect, prices, low, high, color):
    draw_rounded_panel(surface, rect, CARD, border=CARD_BORDER, radius=16)

    label = render_tracked(font_small, "24H RANGE", TEXT_FAINT, tracking=2)
    surface.blit(label, (rect.left + 16, rect.top + 12))

    range_text = f"{fmt_price(low)} - {fmt_price(high)}"
    range_surf = font_small.render(range_text, True, TEXT_MUTED)
    surface.blit(range_surf, range_surf.get_rect(topright=(rect.right - 16, rect.top + 12)))

    plot_rect = pygame.Rect(rect.left + 14, rect.top + 34, rect.width - 28, rect.height - 46)
    if len(prices) < 2:
        return

    fill_surface, points = render_area_chart(prices, plot_rect.width, plot_rect.height, color)
    if fill_surface is None:
        return

    surface.blit(fill_surface, plot_rect.topleft)

    for frac in (0.33, 0.66):
        y = plot_rect.top + int(plot_rect.height * frac)
        pygame.draw.line(surface, GRIDLINE, (plot_rect.left, y), (plot_rect.right, y), 1)

    offset_points = [(plot_rect.left + x, plot_rect.top + y) for x, y in points]
    pygame.draw.lines(surface, color, False, offset_points, 2)

    ex, ey = offset_points[-1]
    draw_filled_circle(surface, ex, ey, 6, blend(CARD, color, 0.30))
    draw_filled_circle(surface, ex, ey, 3, color)


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------

def render_crypto_slide(name, coin, index, total):
    screen.fill(BG)
    logo = load_logo_rounded(coin['logo_url'], size=(28, 28), radius=7)
    render_header(screen, logo, name, coin['tint'])

    price, change = fetch_price(coin)

    if price is not None:
        price_surf = font_price.render(f"${price:,.2f}", True, TEXT_PRIMARY)
        price_rect = price_surf.get_rect(center=(SCREEN_WIDTH // 2, 106))
        screen.blit(price_surf, price_rect)
        pill_bottom = render_change_pill(screen, change, price_rect.bottom + 14)
    else:
        error_surf = font_price.render("--", True, TEXT_FAINT)
        error_rect = error_surf.get_rect(center=(SCREEN_WIDTH // 2, 106))
        screen.blit(error_surf, error_rect)
        pill_bottom = error_rect.bottom + 30

    prices, low, high = fetch_chart_data(coin)
    chart_top = max(pill_bottom + 12, 190)
    chart_rect = pygame.Rect(PAD_X, chart_top, SCREEN_WIDTH - PAD_X * 2, SCREEN_HEIGHT - chart_top - 30)
    render_chart_card(screen, chart_rect, prices, low, high, GREEN if change >= 0 else RED)

    render_dots(screen, index, total, SCREEN_HEIGHT - DOTS_BOTTOM_MARGIN)
    pygame.display.flip()


def render_weather_slide(index, total):
    screen.fill(BG)

    city_label = render_tracked(font_small, WEATHER['label'].upper(), TEXT_MUTED, tracking=3)
    screen.blit(city_label, city_label.get_rect(midtop=(SCREEN_WIDTH // 2, HEADER_TOP + 4)))

    data = fetch_weather()

    if data is not None:
        icon_cy = 72
        draw_weather_icon(screen, SCREEN_WIDTH // 2, icon_cy, 50, weather_icon_kind(data['code']))

        temp_text = f"{data['temp']:.1f}°"
        temp_surf = font_wx_temp.render(temp_text, True, TEXT_PRIMARY)
        screen.blit(temp_surf, temp_surf.get_rect(midtop=(SCREEN_WIDTH // 2, icon_cy + 32)))

        forecasts = data['forecasts']
        card_gap = 8
        card_w = (SCREEN_WIDTH - PAD_X * 2 - card_gap * (len(forecasts) - 1)) // max(len(forecasts), 1)
        card_h = 118
        card_top = SCREEN_HEIGHT - 24 - card_h
        x = PAD_X
        for f in forecasts:
            rect = pygame.Rect(x, card_top, card_w, card_h)
            draw_rounded_panel(screen, rect, CARD, border=CARD_BORDER, radius=12)

            day = datetime.datetime.strptime(f['date'], "%Y-%m-%d").strftime("%a").upper()
            day_surf = render_tracked(font_label, day, TEXT_FAINT, tracking=1)
            screen.blit(day_surf, day_surf.get_rect(midtop=(rect.centerx, rect.top + 9)))

            draw_weather_icon(screen, rect.centerx, rect.top + 54, 44, weather_icon_kind(f['code']))

            max_surf = font_forecast_temp.render(f"{f['max']:.0f}°", True, TEXT_PRIMARY)
            min_surf = font_forecast_temp.render(f"{f['min']:.0f}°", True, TEXT_FAINT)
            temps_w = max_surf.get_width() + 6 + min_surf.get_width()
            temps_x = rect.centerx - temps_w // 2
            temps_y = rect.bottom - 30
            screen.blit(max_surf, (temps_x, temps_y))
            screen.blit(min_surf, (temps_x + max_surf.get_width() + 6, temps_y))

            x += card_w + card_gap
    else:
        error_surf = font_price.render("--", True, TEXT_FAINT)
        screen.blit(error_surf, error_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))

    render_dots(screen, index, total, SCREEN_HEIGHT - DOTS_BOTTOM_MARGIN)
    pygame.display.flip()


def render_slide(index):
    name = SLIDE_NAMES[index]
    if name == 'weather':
        render_weather_slide(index, len(SLIDE_NAMES))
    else:
        render_crypto_slide(name, COINS[name], index, len(SLIDE_NAMES))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    idx = 0
    last_switch = time.time()
    SWITCH_INTERVAL = 30  # seconds

    touch_start = None
    touch_time = None
    show_arrow = False
    arrow_dir = None
    ARROW_DISPLAY_TIME = 2
    arrow_start_time = None

    def draw_arrow(direction):
        arrow_color = TEXT_PRIMARY
        if direction == 'left':
            arrow_surf = font_arrow.render("←", True, arrow_color)
            arrow_rect = arrow_surf.get_rect(center=(SCREEN_WIDTH // 6, SCREEN_HEIGHT // 2))
        else:
            arrow_surf = font_arrow.render("→", True, arrow_color)
            arrow_rect = arrow_surf.get_rect(center=(SCREEN_WIDTH * 5 // 6, SCREEN_HEIGHT // 2))
        screen.blit(arrow_surf, arrow_rect)
        pygame.display.flip()

    render_slide(idx)

    while True:
        now = time.time()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.MOUSEBUTTONDOWN:
                touch_start = event.pos
                touch_time = now
                show_arrow = False
                arrow_dir = None
                arrow_start_time = None
            elif event.type == pygame.MOUSEBUTTONUP and touch_start is not None:
                x_start, y_start = touch_start
                x_end, y_end = event.pos
                dx = x_end - x_start
                dt = now - touch_time if touch_time else 0

                if abs(dx) > 50 and dt < 1.0:  # swipe
                    idx = (idx - 1) % len(SLIDE_NAMES) if dx > 0 else (idx + 1) % len(SLIDE_NAMES)
                    render_slide(idx)
                    last_switch = now
                else:
                    x, y = event.pos
                    if x < SCREEN_WIDTH // 3:
                        idx = (idx - 1) % len(SLIDE_NAMES)
                    elif x > SCREEN_WIDTH * 2 // 3:
                        idx = (idx + 1) % len(SLIDE_NAMES)
                    render_slide(idx)
                    last_switch = now

                touch_start = None
                touch_time = None
                show_arrow = False
                arrow_dir = None
                arrow_start_time = None

        if touch_start is not None and touch_time is not None:
            dt = now - touch_time
            if dt > 0.5 and not show_arrow:
                x, _ = touch_start
                if x < SCREEN_WIDTH // 3:
                    arrow_dir = 'left'
                elif x > SCREEN_WIDTH * 2 // 3:
                    arrow_dir = 'right'
                else:
                    arrow_dir = None

                if arrow_dir:
                    render_slide(idx)
                    draw_arrow(arrow_dir)
                    show_arrow = True
                    arrow_start_time = now

        if show_arrow and arrow_start_time is not None and now - arrow_start_time > ARROW_DISPLAY_TIME:
            show_arrow = False
            arrow_dir = None
            arrow_start_time = None
            render_slide(idx)

        if now - last_switch > SWITCH_INTERVAL and not show_arrow and touch_start is None:
            idx = (idx + 1) % len(SLIDE_NAMES)
            render_slide(idx)
            last_switch = now

        time.sleep(0.01)


if __name__ == "__main__":
    main()
