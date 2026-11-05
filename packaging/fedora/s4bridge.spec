# Fedora / RPM packaging. Build:  rpmbuild -ba s4bridge.spec  (with the release tarball in SOURCES)
Name:           s4bridge
Version:        0.4.1
Release:        1%{?dist}
Summary:        Use the original Traktor Kontrol S4 (MK1) with Mixxx and any MIDI software
License:        GPL-3.0-or-later
URL:            https://github.com/fancybutler/s4bridge
Source0:        %{url}/archive/refs/tags/v%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  systemd-rpm-macros
Requires:       python3-pyside6
Requires:       python3-evdev
Requires:       alsa-lib
Recommends:     mixxx

%description
The original Traktor Kontrol S4 only ever worked with Traktor. S4 Bridge turns it into a full
MIDI controller with LED feedback for Mixxx, DAWs and any MIDI software.

%prep
%autosetup

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files s4bridge
install -Dm644 packaging/70-s4bridge.rules %{buildroot}%{_udevrulesdir}/70-s4bridge.rules
install -Dm644 packaging/s4bridge.desktop %{buildroot}%{_datadir}/applications/s4bridge.desktop
install -Dm644 packaging/s4bridge.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/s4bridge.svg
install -Dm644 packaging/io.github.fancybutler.s4bridge.metainfo.xml -t %{buildroot}%{_metainfodir}/
install -Dm644 packaging/s4bridge.service %{buildroot}%{_userunitdir}/s4bridge.service

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/s4bridge
%{_udevrulesdir}/70-s4bridge.rules
%{_datadir}/applications/s4bridge.desktop
%{_datadir}/icons/hicolor/scalable/apps/s4bridge.svg
%{_metainfodir}/io.github.fancybutler.s4bridge.metainfo.xml
%{_userunitdir}/s4bridge.service

%changelog
* Wed Nov 04 2026 Fancy Butler - 0.4.0-1
- See CHANGELOG.md
