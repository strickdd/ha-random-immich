# Immich Random Image for Home Assistant

![GitHub Release](https://img.shields.io/github/v/release/strickdd/ha-random-immich)
![License](https://img.shields.io/github/license/strickdd/ha-random-immich)

A custom integration for Home Assistant that displays random images from your [Immich](https://immich.app) instance on your dashboards. Built for Immich v3+ — the old `immich-home-assistant` integration broke when Immich changed their API in v3, so this is a fresh implementation using the current `/api/search/random` endpoint.

## Features

- **Fully random image** from your entire Immich library
- **Random image from a specific album** — select one album in options
- **Random image from multiple albums** — select multiple albums; the integration picks randomly across all of them
- **SSL toggle** — disable SSL verification for self-hosted instances without valid certificates
- **URL normalization** — handles `localhost`, `127.0.0.1`, private IPs, bare hostnames, and full domain names
- **Configurable refresh interval** — new image every 5 minutes by default
- **Metadata attributes** — filename, dimensions, and capture date exposed as state attributes
- **No external dependencies** — uses only `aiohttp` (bundled with Home Assistant)

## Installation

Install via [HACS](https://hacs.xyz) (Home Assistant Community Store).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=ha-random-immich&category=Integration&owner=strickdd)

1. Click the button above, or open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/strickdd/ha-random-immich` as an Integration repository
3. Install "Immich Random Image" from HACS
4. Restart Home Assistant

### Manual installation

Copy the entire `custom_components/immich_random/` directory into your Home Assistant `custom_components/` directory, then restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=immich_random)

1. Click the button above, or go to **Settings → Devices & Services → Add Integration**
2. Search for "Immich Random Image"
3. Enter your Immich server URL and API key
   - Generate an API key in Immich under **Settings → API Keys**
   - Toggle SSL verification off if your self-hosted instance uses self-signed certificates
4. After setup, click **Configure** on the integration to select which albums to pull from
   - Leave all albums unchecked for a fully random image from your entire library
   - Select one album for random images from that album only
   - Select multiple albums for random images across all selected albums

## Usage

Add the entity to your dashboard using a Picture card or Picture Entity card:

```yaml
type: picture-entity
entity: image.immich_random_album_image
show_state: false
show_name: false
aspect_ratio: "16:9"
fit_mode: contain
```

Or use it as a dashboard background image:

```yaml
type: picture
image_entity: image.immich_random_album_image
```

The entity refreshes every 5 minutes with a new random image. State attributes include `media_filename`, `media_localdatetime`, `media_width`, and `media_height`.

## How it works

The integration uses Immich's `/api/search/random` endpoint (introduced in Immich v3) to request a single random image, optionally filtered by album IDs. It then downloads the original full-resolution image and serves it as a standard Home Assistant `image` entity. No asset ID caching or listing is needed — the random endpoint handles selection server-side.

## Requirements

- Home Assistant 2024.1+ (tested on 2026.8.0)
- Immich v3+ running and accessible from your Home Assistant instance
- A long-lived Immich API key

## License

MIT
