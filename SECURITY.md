# Security Policy

## Supported Versions

The following versions of `highrise-bot-python` are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within this project, please report it responsibly.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please send an email to the repository owner or open a private security advisory on GitHub.

### What to Include

When reporting a vulnerability, please include as much of the following information as possible:

- **Description** of the vulnerability
- **Steps to reproduce** the issue
- **Affected versions** (if known)
- **Potential impact** of the vulnerability
- **Any suggested fixes** or mitigations (optional)

### What to Expect

- **Acknowledgment**: You will receive an acknowledgment of your report within **48 hours**.
- **Assessment**: The maintainer will assess the vulnerability and determine its severity.
- **Resolution**: If the vulnerability is confirmed, a fix will be developed and released as soon as possible.
- **Credit**: With your permission, you will be credited for the discovery in the release notes.

## Security Best Practices for Users

This SDK is **unofficial** and is not affiliated with, endorsed by, or supported by Highrise or Pocket Worlds. When using this SDK in production, please follow these guidelines:

### API Tokens

- **Never commit API tokens** to version control.
- Use environment variables or secure secret management solutions to store tokens.
- Rotate your API tokens regularly.
- If you suspect a token has been compromised, revoke it immediately via the Highrise developer portal.

### Dependencies

- Keep `aiohttp` and `orjson` up to date.
- Run `pip audit` or a similar tool to check for known vulnerabilities in dependencies.
- Review the dependencies of this SDK before deployment.

### Network Security

- The SDK connects to `wss://highrise.game` for the WebSocket API and `https://webapi.highrise.game` for the Web API.
- Ensure your environment has proper TLS verification enabled (this is the default in `aiohttp`).
- Be aware that bot traffic is visible to the Highrise platform.

### General

- This SDK favors **throughput over strict validation**. Do not rely on it for validating untrusted input without additional sanitization.
- Run your bot with the **least privileges** necessary.
- Monitor your bot's logs for unexpected errors or behavior.

## Disclaimer

This software is provided "AS IS", without warranty of any kind, express or implied. See [LICENSE.md](./LICENSE.md) for the full license text.
