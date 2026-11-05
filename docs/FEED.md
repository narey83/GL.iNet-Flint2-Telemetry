# Signed community package feed

Feed page: **https://narey83.github.io/GL.iNet-Flint2-Telemetry/**

This is a community feed for **GL.iNet Flint 2 / GL-MT6000, vendor OpenWrt 21.02,
musl, fw3/iptables, aarch64_cortex-a53 only**. It is not an official OpenWrt feed.
It is not qualified for stock newer OpenWrt, fw4/nftables, APK, other CPU ABIs or
other routers, even when they report the same architecture name.

## Register the feed through LuCI

1. Open the [feed page](https://narey83.github.io/GL.iNet-Flint2-Telemetry/).
2. Download `flint2-telemetry-feed_1.0-1_aarch64_cortex-a53.ipk` and its `.sha256` file.
   Verify the checksum before uploading. For example, from their download directory:
   ```sh
   sha256sum -c flint2-telemetry-feed_1.0-1_aarch64_cortex-a53.ipk.sha256
   # macOS:
   shasum -a 256 -c flint2-telemetry-feed_1.0-1_aarch64_cortex-a53.ipk.sha256
   ```
3. In LuCI, open **System → Software → Upload Package**, select the setup IPK and
   install it. Its pre-install check requires the running GL-MT6000 board,
   OpenWrt 21.02 and fw3. Do not force installation on an unsupported device.
4. Click **Update lists**, search for **flint2-telemetry**, and install it.
5. Open **Services → Flint2 Telemetry** and configure your own HTTPS destination,
   output choices and monitored interfaces, then enable telemetry and Save & Apply.

Installing the setup IPK trusts this project's public package-signing key. The first
setup download is bootstrapped through HTTPS and the published checksum; subsequent
feed indexes are checked against that installed key. The setup package adds only:

- `/etc/opkg/flint2-telemetry.conf`, its own feed definition.
- `/etc/opkg/keys/85cd62be71053c3e`, the public verification key.
- Its license notice.

It does not edit vendor `distfeeds.conf` or `customfeeds.conf`, disable signature
checks, install the telemetry agent, or start a service. The plain-text feed index
labels telemetry as **GL-MT6000 vendor OpenWrt 21.02 / musl / fw3 only**, so LuCI's
available-package description also shows the compatibility limit.

## Trust identity

The public key is tracked in
[`feed/keys/flint2-telemetry.pub`](../feed/keys/flint2-telemetry.pub).

```text
usign fingerprint: 85cd62be71053c3e
public-key SHA-256: 20e32ff6c0e948438e56c320efd29393778f00102f7b1a2028401cb0e7d800a5
setup-IPK SHA-256: 4a02b0932dffca9134724facf86ea31b4c404b914629e3a1708448c98c1815ff
```

Private signing material is not in the repository, Pages output or setup IPK.
The feed publisher signs the uncompressed `Packages` file with OpenWrt's usign;
`Packages.gz` carries the same index, and each entry includes the IPK's SHA-256 and
size. A checksum alone is not a signature. Keep opkg signature verification enabled.

## Manual registration

If you prefer SSH, download the public key and verify its full hash before adding
it. These commands trust only the published project key:

```sh
curl --fail --location --proto '=https' \
  'https://narey83.github.io/GL.iNet-Flint2-Telemetry/flint2-telemetry.pub' \
  -o /tmp/flint2-telemetry.pub
printf '%s\n' '20e32ff6c0e948438e56c320efd29393778f00102f7b1a2028401cb0e7d800a5  /tmp/flint2-telemetry.pub' \
  | sha256sum -c -
opkg-key add /tmp/flint2-telemetry.pub
```

Then add this **one line** under LuCI's **System → Software → Configure opkg →
customfeeds.conf**, preserving existing entries:

```text
src/gz flint2_gl_mt6000_21_02 https://narey83.github.io/GL.iNet-Flint2-Telemetry/feeds/gl-mt6000/openwrt-21.02/aarch64_cortex-a53
```

Use either the setup IPK or manual registration, not both, to avoid duplicate feed
entries. Run `opkg update` or click Update lists. Then install with LuCI or
`opkg install flint2-telemetry`.

## Updates, configuration and removal

After a new qualified release is published and feed deployment succeeds, click
**Update lists** in LuCI. The package can then appear as upgradable. Upgrade only
the intended package; do not perform an indiscriminate system-wide opkg upgrade.
Existing `/etc/config/flint2` is a conffile. Back up your configuration and separately
managed CA/header files; firmware updates may require reinstalling the package.
A feed does not guarantee packages survive a firmware flash.

Only the current telemetry version is advertised for installation/upgrade, plus
the feed setup package. Up to 20 published stable release IPKs and their matching
source archives are retained on the site for recent cached indexes and manual
rollback. Drafts and prereleases do not become feed candidates. Qualification
notes remain in [GitHub Releases](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases).
The index does not claim support for a newer ABI just because a build exists.

To remove registration installed by the setup IPK, remove `flint2-telemetry-feed`
in LuCI or run `opkg remove flint2-telemetry-feed`. If its feed configuration was
modified, opkg can preserve it as a modified conffile; remove the retained feed
entry explicitly if necessary. This does not remove telemetry itself or its data.
For manual registration, remove only the matching custom-feed line and remove the
project key with `opkg-key remove` using the downloaded public-key file, provided
no other configured feed relies on that key.

## Publishing and key maintenance

The [Publish signed Flint2 feed workflow](../.github/workflows/feed.yml) runs after
a release is published, or manually from `main`. It checks out publisher code from
`main`, verifies stable release assets, tagged commit, target ABI, generic disabled
profile, capture hash and corresponding source contents. It signs the index and
verifies that signature before handing only the public site directory to Pages.
A failed validation leaves the currently deployed site in place.

The signing key is the repository Actions secret `FLINT2_FEED_SIGNING_KEY`. It is
available only to the signing step, written temporarily outside the publish
directory and removed on step exit. Pages deployment uses its own restricted job
with `pages: write` and `id-token: write`; it does not receive the signing secret.
No pull-request workflow signs or deploys a feed. The signing tool is built from
checksum-pinned official OpenWrt usign source.

Keep the owner's offline key backup secure. Losing the private key requires a new
key and an explicit client trust update; changing the public key alone cannot
make existing clients trust it. Rotate the bootstrap package version, documented
fingerprint/hash and publisher identity together. Never commit a private signing
key or turn off signature checking to work around a failed update.

Before publishing a new target ABI, add a separate qualified feed lane and tests.
Do not replace this 21.02 feed with packages for newer firmware. If the latest
stable release does not match this lane, the current publisher fails rather than
signing a package for an incompatible firmware.
