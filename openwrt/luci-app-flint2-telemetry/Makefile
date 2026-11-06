include $(TOPDIR)/rules.mk

PKG_VERSION:=0.4.0
PKG_RELEASE:=1
PKG_MAINTAINER:=John Narey <john.narey@gmail.com>
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=root/usr/share/licenses/luci-app-flint2-telemetry/LICENSE

LUCI_TITLE:=LuCI support for Flint2 Telemetry
LUCI_MAINTAINER:=John Narey <john.narey@gmail.com>
LUCI_DEPENDS:=+luci-base +flint2-telemetry
LUCI_PKGARCH:=all

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
