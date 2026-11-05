#!/usr/bin/env bash
# Build release artifacts and refresh the AUR PKGBUILD for the current version.
# Usage: tools/make-release.sh        (run from the repo root, after tagging vX.Y.Z)
set -euo pipefail
ver=$(python3 -c "import s4bridge; print(s4bridge.__version__)")
echo "S4 Bridge $ver"
python3 -m pytest -q tests
rm -rf dist && python3 -m build
git archive --format=tar.gz --prefix="s4bridge-$ver/" -o "dist/s4bridge-$ver.tar.gz" "v$ver"
sum=$(sha256sum "dist/s4bridge-$ver.tar.gz" | cut -d' ' -f1)
sed -i "s/^pkgver=.*/pkgver=$ver/; s/^sha256sums=.*/sha256sums=('$sum')/" packaging/aur/PKGBUILD
sed -i "s/^Version:.*/Version:        $ver/" packaging/fedora/s4bridge.spec
(cd packaging/aur && makepkg --printsrcinfo > .SRCINFO) 2>/dev/null || echo "(run makepkg --printsrcinfo on Arch to refresh .SRCINFO)"
echo "dist/ ready; AUR PKGBUILD updated to $ver ($sum)"
