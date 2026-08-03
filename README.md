# mihomo-webui-config

English | [简体中文](README.zh-CN.md)

Thin Arch/AUR integration for Mihomo, MetaCubeXD, and safe subscription updates.

The package does not ship a Mihomo core or WebUI copy. It depends on `mihomo`
and `metacubexd-bin`, installs conservative templates, and provides
`mihomo-subscription` to maintain one aggregated file provider:

```text
/etc/mihomo/providers/subscriptions.yaml
```

Regular subscription updates never rewrite `/etc/mihomo/config.yaml`.

New configurations enable Mihomo's built-in DNS with explicit mainland-China
upstreams and never use `nameserver: system`. This prevents a DNS loop when a
Linux TUN takes over systemd-resolved. TUN remains disabled by default; if it
is enabled manually, keep every Mihomo DNS upstream independent of the system
resolver.

The package explicitly depends on AUR `mihomo-bin` and `clash-geoip`, and links
the latter's database into `/etc/mihomo/Country.mmdb`. The fallback filter
intentionally avoids `geosite: gfw` because `mihomo-bin` does not provide
`GeoSite.dat`.

## Install Flow

```bash
paru -S mihomo-webui-config
mihomo-webui-setup
```

For a manual source build, install the AUR dependencies first:

```bash
paru -S --needed mihomo-bin metacubexd-bin clash-geoip
makepkg -si
```

The setup command requests administrator privileges itself, prompts for the
subscription URL without echoing it, prepares and starts a local subconverter
when the selected source format needs one, performs the first strict update,
and enables Mihomo plus the subscription timer. Existing configuration files
and an existing `pref.ini` are preserved.

For manual or multi-source configuration, the individual
`mihomo-subscription init` and `update` commands remain available.

For a routine manual update, use the setup command's update subcommand. It
requests administrator privileges itself and reloads or restarts Mihomo after
a successful update:

```bash
mihomo-webui-setup update
mihomo-webui-setup update --strict
```

After a package upgrade, rebuild the main config from the latest template:

```bash
paru -Syu
mihomo-webui-setup reset
```

`reset` keeps the subscription URLs, `subscriptions.yaml` (including
converter settings), the API secret, `external-controller`, `allow-lan`
together with `bind-address`/`lan-allowed-ips`/`lan-disallowed-ips`, proxy
authentication and `skip-auth-prefixes`, proxy listen ports, and the current
`tun` block. DNS, proxy groups, rules, and provider definitions are
regenerated from the package's latest `config.base.yaml`, so new security
defaults are picked up automatically. The candidate config and a freshly
downloaded provider are validated with `mihomo -t` before anything is
replaced; if replacement or reload fails, the original config and provider
are rolled back. Use `reset --yes` for automation and `reset --dry-run` to
preview without writing files.

For a server whose WebUI/API should be reachable on a trusted LAN, bind the
controller to the server's LAN address during the first setup. This does not
expose the proxy port unless `--allow-proxy-lan` is also passed:

```bash
mihomo-webui-setup --controller-listen 192.168.1.10:9090
```

Binding the controller to `0.0.0.0` also exposes it on public interfaces when
present. Prefer a specific LAN/VPN address, or restrict port 9090 with a
firewall. The generated API secret remains required by MetaCubeXD.

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
- provider files are readable by the `mihomo` service user (`root:mihomo`, `0640`; group configurable via `provider_group`).
- services that do not support `systemctl reload` are restarted instead.
- update validates the candidate provider with `mihomo -t` before replacing it.
- `reset` validates the candidate main config plus provider with `mihomo -t`
  before replacing anything, keeps a `config.yaml.bak` backup, and rolls back
  the original config and provider if replacement or reload fails.
- failed sources fall back to cached provider data when available.
- package install does not enable services or perform network access.

## Development Checks

```bash
python -m py_compile mihomo-subscription
pytest
shellcheck mihomo-webui-setup
shellcheck mihomo-webui-config.install
namcap PKGBUILD
updpkgsums
makepkg --printsrcinfo > .SRCINFO
```
