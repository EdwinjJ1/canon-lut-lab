#!/bin/sh
set -eu
CANON_APP='/Applications/Canon Utilities/EOS Utility/EU3/EOS Utility 3.app'
if [ ! -d "$CANON_APP/Contents/Frameworks" ] || [ ! -d "$CANON_APP/Contents/PlugIns" ]; then
  echo 'EOS Utility 3 was not found at the tested location.' >&2
  exit 1
fi
mkdir -p build/R7LutTool.app/Contents/MacOS
ln -sfn "$CANON_APP/Contents/Frameworks" build/R7LutTool.app/Contents/Frameworks
ln -sfn "$CANON_APP/Contents/PlugIns" build/R7LutTool.app/Contents/PlugIns
cat > build/R7LutTool.app/Contents/Info.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>eds_snapshot</string>
<key>CFBundleIdentifier</key><string>local.canonr7lutlab.tool</string>
<key>CFBundleName</key><string>R7 LUT Tool</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>NSCameraUsageDescription</key><string>Read connected Canon camera properties and install an explicitly selected R7 Picture Style.</string>
</dict></plist>
PLIST
clang -fobjc-arc -framework Foundation -framework AppKit src/eds_snapshot.m -o build/R7LutTool.app/Contents/MacOS/eds_snapshot
clang -fobjc-arc -framework Foundation -framework AppKit src/eds_install_one.m -o build/R7LutTool.app/Contents/MacOS/eds_install_one
printf '%s\n' 'Built read-only snapshot and single-slot installer in build/R7LutTool.app/Contents/MacOS/'
