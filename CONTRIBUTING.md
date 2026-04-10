# Contributing

Thanks. Keep changes small, clear, and easy to review.

## Before you open a PR

- search existing issues and pull requests first
- open an issue if the change is large or changes behavior
- keep one pull request focused on one problem

## Development notes

- Android app entry point: `main.py`
- foreground proxy service: `services/proxy_service.py`
- proxy core: `proxy/tg_ws_proxy.py`
- mobile UI: `ui/index.html`

## What we expect

- explain what changed and why
- do not mix unrelated refactors into one PR
- keep behavior changes explicit
- update docs when behavior or setup changes
- do not commit secrets, keystores, or personal credentials

## PR checklist

- the change solves one clear problem
- the diff is readable
- docs are updated if needed
- manual test steps are included

## Good issue reports

Please include:

- device and Android version
- app version if known
- what you expected
- what actually happened
- steps to reproduce
- logs or screenshots if they help

## Contact

If you want to discuss a change before writing code:

- https://t.me/mansurov_rafael
