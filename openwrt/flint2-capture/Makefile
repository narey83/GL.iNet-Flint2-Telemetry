include $(TOPDIR)/rules.mk

PKG_NAME:=flint2-capture
PKG_VERSION:=1.7.9
PKG_RELEASE:=1
PKG_SOURCE:=pmacct-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://github.com/pmacct/pmacct/releases/download/v$(PKG_VERSION)/
PKG_HASH:=94185c33d659772035c63be0a82601bb9eb064fb4be1d68ba279b47204b2750a
PKG_BUILD_DIR:=$(BUILD_DIR)/pmacct-$(PKG_VERSION)
PKG_MAINTAINER:=John Narey <john.narey@gmail.com>
PKG_LICENSE:=GPL-2.0-or-later BSD-3-Clause ISC
PKG_LICENSE_FILES:=COPYING src/external_libs/libcdada/LICENSE
PKG_BUILD_PARALLEL:=1
PKG_FIXUP:=autoreconf

# Release archives include libcdada; never discover a containing buildroot git
# repository and try to initialize pmacct's submodule in that unrelated tree.
export GIT_CEILING_DIRECTORIES:=$(BUILD_DIR)

include $(INCLUDE_DIR)/package.mk

define Package/flint2-capture
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Flint2 IPv4 flow capture component
  URL:=https://github.com/narey83/GL.iNet-Flint2-Telemetry
  DEPENDS:=@ARCH_64BIT +libpcap +libstdcpp
endef

define Package/flint2-capture/description
 Source-built pmacct capture and NetFlow v5 exporter for the local Flint2
 telemetry agent. Includes shared-memory publication and layout-query patches.
endef

CONFIGURE_ARGS += \
	--with-pcap-includes=$(STAGING_DIR)/usr/include \
	--with-pcap-libs=$(STAGING_DIR)/usr/lib \
	--disable-bgp-bins --disable-bmp-bins --disable-st-bins

define Package/flint2-capture/install
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/src/pmacctd $(1)/usr/sbin/flint2-capture
	$(INSTALL_DIR) $(1)/usr/share/licenses/flint2-capture
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/COPYING $(1)/usr/share/licenses/flint2-capture/
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/src/external_libs/libcdada/LICENSE $(1)/usr/share/licenses/flint2-capture/libcdada-LICENSE
endef

$(eval $(call BuildPackage,flint2-capture))
