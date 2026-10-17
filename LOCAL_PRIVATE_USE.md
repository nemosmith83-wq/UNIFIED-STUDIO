# Private-use setup

This package is designed to run on a Windows PC. `START.bat` binds the backend to `127.0.0.1` (the same PC only). On first run it creates `.env` from `.env.example`; add only the provider credentials you intend to use.

For phone/tablet access, `START_MOBILE.bat` binds to all local network interfaces. Use that only on a trusted private Wi-Fi network, keep the host firewall enabled, and stop the process when finished. Do not port-forward the port or expose this development server publicly.

The code-execution feature is application-restricted, not an operating-system sandbox. Keep the server private and do not provide accounts to untrusted users. The package has no production deployment hardening or dependency lockfile.

For voice work, use recordings and voice models you have permission to use. PromptVault Pro's RVC panel embeds the Gradio address you supply. Do not enter an address you do not control or trust.
