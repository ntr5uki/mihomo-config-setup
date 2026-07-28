# Maintainer: ntr5uki <hzy_bme@pku.edu.cn>

pkgname=mihomo-webui-config
pkgver=0.1.0
pkgrel=1
pkgdesc="Mihomo and MetaCubeXD integration with safe subscription updates"
arch=('any')
url="https://github.com/REPLACE_OWNER/mihomo-webui-config"
license=('MIT')

depends=(
  'mihomo'
  'metacubexd-bin'
  'python'
  'python-yaml'
)

optdepends=(
  'subconverter-bin: convert raw URI or Base64 subscriptions locally'
)

install=mihomo-webui-config.install

# 本仓库即 AUR 仓库：src/ 目录下的文件在无 source 声明时与 $srcdir 重合，
# 因此 package() 直接引用 $srcdir 下的文件。仅 LICENSE 位于仓库根目录，
# 需要声明为 source 以便 makepkg 将其链接进 $srcdir。
source=('LICENSE')
md5sums=('38efd55eae1bb89892144dc23099e0ec')

package() {
  install -Dm755 \
    "$srcdir/mihomo-subscription" \
    "$pkgdir/usr/bin/mihomo-subscription"

  install -Dm644 \
    "$srcdir/config.base.yaml" \
    "$pkgdir/usr/share/$pkgname/config.base.yaml"

  install -Dm644 \
    "$srcdir/subscriptions.example.yaml" \
    "$pkgdir/usr/share/$pkgname/subscriptions.example.yaml"

  install -Dm644 \
    "$srcdir/secrets.env.example" \
    "$pkgdir/usr/share/$pkgname/secrets.env.example"

  install -Dm644 \
    "$srcdir/mihomo-subscription-update.service" \
    "$pkgdir/usr/lib/systemd/system/mihomo-subscription-update.service"

  install -Dm644 \
    "$srcdir/mihomo-subscription-update.timer" \
    "$pkgdir/usr/lib/systemd/system/mihomo-subscription-update.timer"

  install -Dm644 \
    "$srcdir/mihomo-webui.conf" \
    "$pkgdir/usr/lib/systemd/system/mihomo.service.d/10-webui.conf"

  install -Dm644 \
    "$srcdir/LICENSE" \
    "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
