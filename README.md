# mihomo-webui-config

Thin Arch/AUR integration for Mihomo, MetaCubeXD, and safe subscription updates.

The package does not ship a Mihomo core or WebUI copy. It depends on `mihomo`
and `metacubexd-bin`, installs conservative templates, and provides
`mihomo-subscription` to maintain one aggregated file provider:

```text
/etc/mihomo/providers/subscriptions.yaml
```

Regular subscription updates never rewrite `/etc/mihomo/config.yaml`.

## Install Flow

```bash
makepkg -si
sudo mihomo-subscription init
sudoedit /etc/mihomo-subscription/subscriptions.yaml
sudoedit /etc/mihomo-subscription/secrets.env
sudo mihomo-subscription update --strict
sudo systemctl enable --now mihomo.service
sudo systemctl enable --now mihomo-subscription-update.timer
```

Open MetaCubeXD at:

```text
http://127.0.0.1:9090/ui/
```

Use the generated secret from `/etc/mihomo/config.yaml`.

## Subscription Design

`/etc/mihomo-subscription/subscriptions.yaml` declares sources. A source can
read its URL directly from the control file or, preferably, from
`/etc/mihomo-subscription/secrets.env`.

Direct mode accepts Clash/Mihomo YAML with `proxies`, provider YAML with
`payload`, or a top-level node list. Raw URI/Base64 subscriptions should be
converted through a local subconverter:

```yaml
converter:
  type: subconverter
  endpoint: http://127.0.0.1:25500/sub
  allow_remote: false
```

Remote converters are rejected by default to avoid leaking subscription tokens.

## Safety Properties

- `external-controller` listens on `127.0.0.1` by default.
- `allow-lan` is disabled by default.
- `init` generates a random Mihomo API secret.
- update logs do not include subscription URLs.
- provider writes are atomic.
- update validates the candidate provider with `mihomo -t` before replacing it.
- failed sources fall back to cached provider data when available.
- package install does not enable services or perform network access.

## Development Checks

```bash
python -m py_compile src/mihomo-subscription
pytest
shellcheck mihomo-webui-config.install
namcap PKGBUILD
updpkgsums
makepkg --printsrcinfo > .SRCINFO
```
