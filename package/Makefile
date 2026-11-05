include $(TOPDIR)/rules.mk

PKG_NAME:=flint2-telemetry
PKG_VERSION:=0.3.1
PKG_RELEASE:=4
PKG_LICENSE:=MIT GPL-2.0-only BSD-3-Clause ISC
PKGARCH:=aarch64_cortex-a53

include $(INCLUDE_DIR)/package.mk

define Package/flint2-telemetry
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Structured Flint2 router telemetry
  DEPENDS:=+lua +lua-cjson +luasocket +luci-lib-nixio +libuci-lua +ubus +curl +ca-bundle +jsonfilter +libstdcpp6 +libgcc1 +sqlite3-cli +coreutils-timeout +iptables
endef

define Build/Compile
endef

define Package/flint2-telemetry/conffiles
/etc/config/flint2
endef

define Package/flint2-telemetry/install
	$(CP) ./files/* $(1)/
	chmod 0755 $(1)/etc/init.d/flint2 $(1)/usr/sbin/flint2-agent $(1)/usr/sbin/flint2-capture $(1)/usr/libexec/flint2/firewall-events
endef

define Package/flint2-telemetry/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
uci set firewall.flint2_events=include
uci set firewall.flint2_events.path=/usr/libexec/flint2/firewall-events
uci set firewall.flint2_events.reload=1
uci commit firewall
rm -f /tmp/luci-indexcache.*
/etc/init.d/flint2 enable
/etc/init.d/flint2 start
endef

define Package/flint2-telemetry/prerm
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
/etc/init.d/flint2 stop
/etc/init.d/flint2 disable
uci -q delete firewall.flint2_events
uci commit firewall
endef

$(eval $(call BuildPackage,flint2-telemetry))
