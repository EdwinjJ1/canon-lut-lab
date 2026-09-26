# Canon R7 LUT Lab — English summary

This project documents an experimentally verified route for converting a pure 3D `.cube` LUT into a Canon EOS R7 user-defined Picture Style that affects live preview and camera JPEGs. It does not modify firmware or add an in-camera CUBE browser.

The tested environment was one R7 on firmware 1.0.1, EOS Utility 3.20.21.3 and Picture Style Editor 1.32.20 on Apple Silicon macOS. The native compiler requires an exact EdsCFParse SHA-256 and a fresh descriptor snapshot from the user's own camera. A normal PF3 must first be registered using Canon's official UI to initialize the target slot. The included installer backs up and writes only the selected slot, verifies a byte-exact readback and checks that its controls remain unchanged.

Start with [the Chinese setup guide](SETUP_ZH.md) or follow the command examples there. [Implementation notes](HOW_IT_WORKS.md), [validation](VALIDATION.md), [input color spaces](INPUT_COLOR.md), and [recovery](RECOVERY.md) are also available. Canon software, camera data, original LUTs, and photos are intentionally excluded. The source code is MIT-licensed; that license does not cover third-party materials.

R5 and other cameras are not validated. The code is an experiment tied to a private native ABI and will stop when its version checks fail.
