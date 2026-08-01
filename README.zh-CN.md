# mihomo-webui-config

[English](README.md) | 简体中文

这是一个面向 Arch Linux/AUR 的轻量集成包，用于部署 Mihomo、MetaCubeXD，
并安全地维护订阅生成的代理 provider。

软件包本身不重复打包 Mihomo 内核或 MetaCubeXD，而是依赖 `mihomo` 和
`metacubexd-bin`，安装保守的默认配置，并提供两个管理命令：

- `mihomo-webui-setup`：一次性安装向导。
- `mihomo-subscription`：初始化、更新和验证订阅。

订阅节点最终聚合到：

```text
/etc/mihomo/providers/subscriptions.yaml
```

日常更新只替换这个 provider，不会重写 `/etc/mihomo/config.yaml`。

## 安装

从 AUR 安装：

```bash
paru -S mihomo-webui-config
```

或者从源码构建：

```bash
git clone https://aur.archlinux.org/mihomo-webui-config.git
cd mihomo-webui-config
makepkg -si
```

安装软件包本身不会启用服务或访问网络。安装完成后由普通用户运行一次向导：

```bash
mihomo-webui-setup
```

向导会自行请求管理员权限，然后完成：

1. 创建 Mihomo、订阅控制文件和密钥文件。
2. 通过隐藏输入读取订阅 URL。
3. 按选择的订阅格式准备本地 subconverter。
4. 下载、聚合并用 Mihomo 校验节点。
5. 启动并启用 `mihomo.service`。
6. 启动订阅定时更新 timer。

已有配置文件和已有 `/opt/subconverter/pref.ini` 不会被覆盖。

## 默认监听与局域网部署

默认配置只允许本机访问：

```yaml
external-controller: 127.0.0.1:9090
allow-lan: false
```

MetaCubeXD 地址为：

```text
http://127.0.0.1:9090/ui/
```

连接 API 时使用 `/etc/mihomo/config.yaml` 中自动生成的随机 `secret`。

服务器部署时，可以在首次创建配置时把 MetaCubeXD/API 绑定到服务器的局域网
或 VPN 地址：

```bash
mihomo-webui-setup --controller-listen 192.168.1.10:9090
```

这只开放 MetaCubeXD/API，不会开放 Mihomo 的代理端口。如果还需要局域网设备
使用 mixed-port，必须单独指定：

```bash
mihomo-webui-setup \
  --controller-listen 192.168.1.10:9090 \
  --allow-proxy-lan
```

这些参数只在新建 `/etc/mihomo/config.yaml` 时生效。已有配置需要手工修改并重新
校验。

不推荐直接绑定 `0.0.0.0:9090`：如果服务器同时有公网网卡，API 也会监听公网。
优先绑定具体的 LAN/VPN 地址，或用防火墙限制 9090 端口的来源网段。

## 更新订阅

定时任务默认在开机约 2 分钟后运行，之后每 6 小时更新一次，并加入最多 10 分钟
的随机延迟：

```bash
systemctl list-timers mihomo-subscription-update.timer
```

手工更新订阅：

```bash
mihomo-webui-setup update
```

普通更新下载失败时会继续使用上一份有效缓存。需要严格检查、禁止缓存回退时：

```bash
mihomo-webui-setup update --strict
```

该命令会自行请求管理员权限。底层管理命令
`sudo mihomo-subscription update [--strict]` 仍然可用于脚本或高级配置。

也可以直接触发与 timer 相同的 systemd 服务：

```bash
sudo systemctl start mihomo-subscription-update.service
sudo systemctl status --no-pager -l mihomo-subscription-update.service
```

更新成功后，如果 Mihomo 不支持 reload，更新器会自动改用 restart，让新节点在
MetaCubeXD 中生效。

需要更换 main 订阅 URL 时：

```bash
sudo mihomo-subscription init
sudo mihomo-subscription update --strict
```

在交互提示中选择不复用旧 URL，然后隐藏输入新的 URL 和正确的订阅格式。

## 订阅格式与 subconverter

`/etc/mihomo-subscription/subscriptions.yaml` 声明订阅来源；URL 推荐保存在权限为
`0600` 的 `/etc/mihomo-subscription/secrets.env` 中。

`direct` 模式可以读取：

- 包含 `proxies` 的 Clash/Mihomo YAML；
- 包含 `payload` 的兼容 provider YAML；
- 顶层为节点列表的 YAML。

原始 URI/Base64 订阅需要本地 subconverter：

```yaml
converter:
  type: subconverter
  endpoint: http://127.0.0.1:25500/sub
  allow_remote: false
```

如果选择这种格式，需要提前安装可提供 `subconverter.service` 的
`subconverter-bin`：

```bash
paru -S subconverter-bin
```

安装向导会自动创建缺失的 `pref.ini`、启动服务并等待 25500 端口就绪。新创建的
配置固定监听 `127.0.0.1`，日志级别为 `warn`，不会默认向局域网暴露转换接口。
远程 subconverter 默认被拒绝，以避免泄露订阅 token。

## 重要路径

| 路径 | 用途 |
| --- | --- |
| `/etc/mihomo/config.yaml` | Mihomo 主配置与 API secret |
| `/etc/mihomo/providers/subscriptions.yaml` | Mihomo 实际加载的聚合节点 |
| `/etc/mihomo-subscription/subscriptions.yaml` | 来源、格式和更新参数 |
| `/etc/mihomo-subscription/secrets.env` | 订阅 URL 等敏感变量 |
| `/var/lib/mihomo-subscription/cache/` | 各来源上一份有效缓存 |
| `/opt/subconverter/pref.ini` | 本地 subconverter 配置 |

## 安全设计

- MetaCubeXD/API 默认只监听 `127.0.0.1:9090`。
- `allow-lan` 默认关闭。
- 本地 subconverter 默认只监听 `127.0.0.1:25500`。
- 初始化时生成随机 Mihomo API secret。
- 更新器日志不会输出订阅 URL。
- provider 使用原子替换，避免写入中途产生半文件。
- provider 默认为 `root:mihomo`、`0640`，Mihomo 服务可读而普通用户不可读。
- 安装候选 provider 前会执行 `mihomo -t` 校验。
- 下载失败时可回退到上一份有效缓存。
- 软件包安装不会自动启用服务或执行网络请求。

注意：subconverter 是独立的第三方程序。较高日志级别可能记录完整订阅 URL，
因此不要公开粘贴其 journal；如果 token 曾暴露，请在订阅服务商处重置链接。

## 状态检查

```bash
systemctl is-active mihomo.service
systemctl is-enabled mihomo.service
systemctl status --no-pager -l mihomo.service

systemctl is-active subconverter.service
systemctl list-timers mihomo-subscription-update.timer
```

查看近期日志：

```bash
sudo journalctl -u mihomo.service -n 50 --no-pager -l
sudo journalctl -u mihomo-subscription-update.service -n 50 --no-pager -l
```

## 开发与发布检查

```bash
python -m py_compile mihomo-subscription
python -m unittest discover -s tests -v
shellcheck mihomo-webui-setup mihomo-webui-config.install
namcap PKGBUILD
makepkg -Ccf
namcap mihomo-webui-config-*.pkg.tar.zst
makepkg --printsrcinfo > .SRCINFO
```
