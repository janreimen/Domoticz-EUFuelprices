# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x-alpha | :white_check_mark: (current) |
| 1.0.0 (original single-file edition) | :x: superseded |

This is a pre-1.0 alpha. Only the latest tag receives fixes.

## Reporting a vulnerability

Please use GitHub's private reporting flow rather than a public issue: go to the **Security** tab on
this repository → **Report a vulnerability**. If that's not available, open an issue asking for a
private channel and avoid details until one is set up.

## Threat model

This plugin runs inside the Domoticz process with the same privileges as Domoticz itself - only install
plugins (this one included) from sources you trust, and read the source before deploying it. That said,
what this specific plugin does is narrow:

- **Outbound only, to one host.** It makes HTTPS `GET` requests to `eurooilwatch.com` (a free, public,
  keyless, read-only API). It accepts no inbound connections and exposes no ports.
- **No secrets.** There is no API key, username, password, or token anywhere in this plugin - there is
  nothing to leak.
- **No third-party dependencies.** The Python standard library only (`urllib`, `json`, `threading`,
  `queue`, `datetime`, `math`). Zero supply-chain surface beyond CPython itself.
- **TLS certificate validation is never disabled.** `urllib.request` uses Python's default `ssl`
  context, which validates certificates; nothing in this codebase overrides that.
- **Bounded response size.** Every fetch caps the response at 1 MiB (`MAX_BYTES`) before attempting to
  parse it, to bound memory use if the endpoint (or a DNS hijack / MITM) ever returns something huge.
- **Strict, fail-loud parsing.** Prices are never substituted with a fabricated value (e.g. zero) when
  missing or malformed - a bad response is rejected with a specific `ValueError` and the plugin simply
  keeps showing the last good value rather than writing bad data into your graphs.
- **Resolved in 0.1.1-alpha:** the 0.1.0-alpha release shipped with a wrong field-name guess for the
  Mode4 reserve sensors. That was a correctness bug, not a security one - the mismatch was silent rather
  than loud (an optional field simply never populated) and never touched anything outside its own three
  sensors. See CHANGELOG.md and DEPLOY.md for details.

## Reporting other issues

Non-security bugs go in regular GitHub issues - see [CONTRIBUTING.md](CONTRIBUTING.md).
