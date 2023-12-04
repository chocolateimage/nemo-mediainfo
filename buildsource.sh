#!/usr/bin/sh

rm -r debian/nemo-mediainfo
gbp buildpackage --git-ignore-new --git-builder='debuild -i -I -S'