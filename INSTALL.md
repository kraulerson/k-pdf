# Installing K-PDF

Download the latest release for your platform from
[GitHub Releases](https://github.com/KarlRaulworx/k-pdf/releases).

## macOS

macOS quarantines all files downloaded from the internet. Because K-PDF is
unsigned, you must clear the quarantine attribute before running it.

```bash
tar xzf K-PDF-*-macos.tar.gz
xattr -cr main.dist
./main.dist/main
```

## Windows

```
# Extract the zip, then double-click main.exe
```

## Linux

```bash
tar xzf K-PDF-*-linux.tar.gz
chmod +x main.dist/main
./main.dist/main
```

## Why not a .app or .dmg on macOS?

Unsigned `.app` bundles downloaded from the internet are blocked by macOS
Gatekeeper with a "damaged and can't be opened" error. Distributing as a
`.tar.gz` with a standalone binary avoids this issue entirely. Users only need
to run `xattr -cr` once after extracting.
