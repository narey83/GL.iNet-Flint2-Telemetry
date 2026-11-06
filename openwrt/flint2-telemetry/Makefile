include $(TOPDIR)/rules.mk

PKG_NAME:=flint2-telemetry
PKG_VERSION:=0.4.0
PKG_RELEASE:=1
FLINT2_SOURCE_VERSION:=83ce2c0d3f45f66dfa3f3fb47b0423abdf1c113a
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/narey83/GL.iNet-Flint2-Telemetry/tar.gz/$(FLINT2_SOURCE_VERSION)?
PKG_HASH:=42c8cc83dd638a8c273e371eb6f189d307c4dafa45627a34a0cffc192afd50af
PKG_BUILD_DIR:=$(BUILD_DIR)/GL.iNet-Flint2-Telemetry-$(FLINT2_SOURCE_VERSION)
PKG_MAINTAINER:=John Narey <john.narey@gmail.com>
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/flint2-telemetry
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Structured router telemetry using ECS and OpenTelemetry
  URL:=https://github.com/narey83/GL.iNet-Flint2-Telemetry
  DEPENDS:=@ARCH_64BIT +flint2-capture +lua +lua-cjson +luasocket +luaposix +libuci-lua +ubus +curl +ca-bundle +jsonfilter +coreutils-timeout +firewall4
endef

define Package/flint2-telemetry/description
 Router health, interface counters, inventory, logs and IPv4 flow observations
 over OTLP/HTTP JSON, ECS NDJSON or GELF HTTPS. Starts disabled; requires the
 user's own destination settings. LuCI configuration is a separate package.
endef

define Build/Compile
endef

define Package/flint2-telemetry/conffiles
/etc/config/flint2
endef

define Package/flint2-telemetry/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/usr/lib/lua/flint2 $(1)/usr/libexec/flint2
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/package/files/usr/sbin/flint2-agent $(1)/usr/sbin/
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/package/files/usr/lib/lua/flint2/*.lua $(1)/usr/lib/lua/flint2/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/package/files/usr/libexec/flint2/* $(1)/usr/libexec/flint2/
	$(INSTALL_DIR) $(1)/etc/init.d $(1)/etc/config $(1)/etc/uci-defaults
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/package/files/etc/init.d/flint2 $(1)/etc/init.d/
	$(INSTALL_CONF) $(PKG_BUILD_DIR)/package/files/etc/config/flint2 $(1)/etc/config/
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/package/files/etc/uci-defaults/90-flint2-telemetry $(1)/etc/uci-defaults/
	$(INSTALL_DIR) $(1)/usr/share/licenses/flint2-telemetry
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/LICENSE $(1)/usr/share/licenses/flint2-telemetry/
endef

define Package/flint2-telemetry/prerm
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
/usr/libexec/flint2/firewall-events stop
uci -q delete firewall.flint2_events || true
uci commit firewall
endef

# APK upgrades otherwise call procd "start" with the same command/config, which
# may retain an already-running Lua process with the previous modules loaded.
# Preserve enablement; the standard post-upgrade hook starts enabled services.
define Package/flint2-telemetry/preinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
if [ "$$PKG_UPGRADE" = 1 ] && [ -x /etc/init.d/flint2 ]; then
	/etc/init.d/flint2 stop
fi
endef

$(eval $(call BuildPackage,flint2-telemetry))
