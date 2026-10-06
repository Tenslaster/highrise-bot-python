# Security Policy

## Overview

`highrise-bot-python` is an unofficial, independent Python SDK implementation for building and operating Highrise bots.

This repository is **not affiliated with, endorsed by, sponsored by, or officially supported by Highrise or Pocket Worlds**. The official Highrise Python SDK remains the reference implementation used by this project for compatibility testing; this project uses its own implementation, validation, request handling, serialization, and runtime architecture.

Security reports concerning this repository are welcome. Please report vulnerabilities privately so they can be investigated and, where appropriate, fixed before public disclosure.

---

## Supported Versions

Security fixes are currently provided for the active `1.0.x` release line.

| Version | Security Support |
| ------- | :--------------: |
| `1.0.x` |    ✅ Supported   |
| `< 1.0` |  ❌ Not supported |

Security support applies to vulnerabilities in the `highrise-bot-python` project itself. Third-party dependencies remain subject to their own security advisories and release policies.

For production deployments, users should keep both this SDK and its dependencies up to date.

---

## Reporting a Vulnerability

### Do not use public GitHub issues

**Please do not disclose security vulnerabilities through public GitHub Issues, pull requests, discussions, comments, or public social media posts.**

Public disclosure before a fix is available can expose other users and bot deployments to unnecessary risk.

### Preferred reporting method

Use GitHub's private vulnerability-reporting or repository security-advisory mechanism when it is available for this repository.

From the repository:

`Security` → `Advisories` / `Report a vulnerability`

Repository:

`https://github.com/Tenslaster/highrise-bot-python`

If private vulnerability reporting is unavailable, contact the maintainer through the repository owner's GitHub profile and request a private reporting channel:

`https://github.com/Tenslaster`

When asking for a secure contact method through a public channel, **do not include exploit details, credentials, tokens, proof-of-concept payloads, or other sensitive information**.

GitHub provides private vulnerability-reporting and repository security-advisory mechanisms specifically for coordinated disclosure and private collaboration between maintainers and security researchers.

---

## What to Include

A useful report should contain as much of the following information as safely possible:

* A clear description of the vulnerability.
* The affected version or version range.
* The affected component, module, function, CLI path, or runtime behavior.
* Steps required to reproduce the issue.
* A minimal proof of concept, when appropriate.
* Expected behavior.
* Actual behavior.
* Security impact and realistic attack scenarios.
* Whether authentication or a Highrise bot token is required.
* Whether the issue requires attacker-controlled network traffic, packet data, configuration, or application input.
* Relevant operating system and Python version information.
* Any known mitigations or workarounds.
* Suggested remediation, when known.

Please redact all credentials and secrets before submitting a report.

**Never include a live Highrise API token, password, session credential, private key, or other authentication secret in a security report.**

---

## Security-Sensitive Areas

The following areas are especially relevant when assessing this project:

### Transport and WebSocket handling

The SDK communicates with the Highrise bot WebSocket service and maintains asynchronous connection state.

Security reports involving any of the following are relevant:

* Authentication or credential leakage.
* TLS verification bypasses.
* Unsafe connection handling.
* Malicious or malformed WebSocket frames.
* Unexpected reconnect behavior.
* Resource exhaustion caused by network input.
* Connection-state corruption.

The project currently uses the Highrise bot WebSocket endpoint:

`wss://highrise.game/web/botapi`

### Web API handling

The project also provides a Web API client for the Highrise API.

Relevant issues include:

* Improper URL handling.
* Unsafe response parsing.
* SSRF-style behavior introduced by SDK functionality.
* Resource exhaustion.
* Unexpected handling of malicious HTTP responses.
* Credential or sensitive-data disclosure.

The documented Web API base URL is:

`https://webapi.highrise.game`

The SDK's Web API client is documented as unauthenticated; Highrise bot tokens are intended for the bot WebSocket API rather than ordinary Web API client calls.

### Validation and packet parsing

The project includes strict validation, semantic validation, structured validation errors, and invalid-packet handling.

Security reports are especially important for issues such as:

* Validation bypasses.
* Parser crashes caused by attacker-controlled data.
* Denial-of-service conditions.
* Excessive CPU or memory consumption.
* Recursion or pathological input behavior.
* Inconsistent strict/lenient behavior that creates a security-sensitive bypass.
* Invalid packets reaching application handlers when they should have been rejected.
* Unsafe processing of malformed nested structures.

The live receive loop uses strict validation by default, with configurable invalid-packet behavior.

### Request lifecycle and cancellation

The SDK maintains pending asynchronous request state and includes cleanup mechanisms for disconnects and cancellation.

Relevant vulnerabilities include:

* Requests remaining permanently pending after connection loss.
* Unbounded pending-request growth.
* Resource leaks.
* Cancellation handling that leaves tasks, futures, or resources alive.
* Cross-request state corruption.
* Unexpected execution after a request has been cancelled.

### Serialization and deserialization

The SDK supports a fast JSON path through `orjson` when installed and falls back to Python's standard-library `json` implementation.

Security reports may include:

* Unsafe serialization behavior.
* Malformed object handling.
* Resource exhaustion.
* Incorrect escaping or encoding that changes protocol semantics.
* Security-sensitive discrepancies between JSON backends.

### CLI and environment handling

The SDK provides a command-line runner and supports environment-based configuration.

Relevant issues include:

* Secrets appearing in logs or error output.
* Unsafe command-line argument handling.
* Environment-variable injection or unsafe configuration behavior.
* Local privilege escalation.
* Sensitive information written to diagnostic output.

---

## Secret and Credential Handling

Highrise bot API tokens must be treated as credentials.

### Never commit secrets

Do not commit:

* Highrise API tokens.
* Passwords.
* Session credentials.
* Private keys.
* Access tokens.
* Bot configuration files containing secrets.
* Production `.env` files or equivalent secret files.

The repository's documented Windows setup uses a local `bot.env.bat` file containing values such as:

```bat
@echo off
set "ROOM_ID=put_your_room_id_here"
set "API_TOKEN=put_your_bot_token_here"
```

That file should remain outside version control.

Example `.gitignore` entries:

```text
bot.env.bat
venv/
logs/
```

### If a token is exposed

Assume an exposed Highrise bot token is compromised.

Immediately:

1. Revoke or rotate the affected token using the appropriate Highrise creator/developer tooling.
2. Replace the credential with a newly issued token.
3. Remove the secret from active configuration.
4. Check Git history and other logs for additional exposure.
5. Determine whether the credential was copied or used elsewhere.
6. Avoid relying only on deleting the latest file or commit; credentials may remain recoverable from repository history.

Do not publish the compromised token while reporting the incident.

---

## Logging and Diagnostic Data

The SDK exposes diagnostics and validation information intended to make malformed packets and runtime behavior easier to understand.

Production deployments should avoid logging sensitive data unnecessarily.

In particular:

* Do not log API tokens.
* Do not log credentials or authentication headers.
* Avoid permanently storing complete raw network packets unless there is a legitimate operational reason.
* Review exception output before sharing it publicly.
* Sanitize logs before attaching them to public issues.
* Use rate-limited validation logging where appropriate.
* Treat raw payloads as potentially untrusted input.

A validation error can contain rejected payload information. Developers should therefore ensure that their own logging and telemetry systems do not unintentionally expose private or sensitive data.

---

## Safe Testing Expectations

Security testing should be performed in an environment you control and in a manner that does not intentionally disrupt Highrise services, other users, or unrelated bot deployments.

Prefer:

* Local unit tests.
* Reproduction against controlled test data.
* Synthetic malformed packets.
* A dedicated development bot.
* A controlled test room.
* Offline parser and validation tests.
* Minimal, non-destructive proof-of-concept code.

Avoid:

* Credential theft or token reuse.
* Testing against accounts you do not control.
* Traffic floods against Highrise infrastructure.
* Attempts to disrupt the Highrise service.
* Destructive automation.
* Public release of an exploit before responsible coordination.

The goal of a security report is to establish and resolve a defect, not to demonstrate maximum operational impact.

---

## Third-Party Dependencies

This project relies on third-party software.

The current project metadata declares:

* `aiohttp>=3.9` as a required runtime dependency.
* `orjson>=3.9` as an optional fast JSON dependency.
* Development dependencies including `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `build`, and `twine`.

Third-party packages are **not relicensed by this repository's custom license**. Their respective copyright notices, licenses, and security advisories remain applicable.

Users deploying this project should:

* Keep dependencies updated.
* Review security advisories affecting their environment.
* Use dependency auditing tools such as `pip audit` where appropriate.
* Pin or otherwise control dependency versions for reproducible deployments.
* Review transitive dependencies before production deployment.

A vulnerability in a dependency should be reported through the appropriate upstream security process when the issue is not caused by this project.

If a dependency vulnerability becomes exploitable specifically because of code in `highrise-bot-python`, report the project-specific issue privately as described above.

---

## Security Architecture Notes

The SDK includes several defensive and operational mechanisms that are relevant to security and reliability:

* Strict packet validation in the live receive loop by default.
* Optional semantic validation for value and protocol constraints.
* Structured validation errors with paths, expected values/types, observed values/types, and reason codes.
* Configurable invalid-packet policies including `drop`, `raise`, and `log-only`.
* Invalid-packet telemetry and diagnostic counters.
* Explicit pending-request failure handling when a transport connection dies.
* Request cleanup through lifecycle management.
* Bot-owned task lifecycle management intended to prevent orphaned asynchronous work.
* Optional fire-and-forget request behavior.
* Standard-library JSON fallback when `orjson` is unavailable.
* Configurable WebSocket and Web API timeouts.

These mechanisms improve robustness, but they are **not a substitute for application-level authorization, access control, input validation, rate limiting, secret management, or secure deployment practices**.

---

## What Is Not a Security Guarantee

Benchmark results, parser performance, compatibility testing, or successful malformed-input tests do not constitute a security certification.

The repository's benchmark suite is intended to measure implementation behavior and performance. It does not establish immunity from:

* Unknown vulnerabilities.
* Dependency vulnerabilities.
* Highrise service vulnerabilities.
* Operating-system vulnerabilities.
* Application-level security bugs.
* Bot business-logic vulnerabilities.
* Misconfiguration.
* Credential compromise.
* Denial-of-service outside the tested conditions.

Likewise, compatibility with the official Highrise SDK does not imply that the project is officially supported by Highrise or Pocket Worlds.

---

## Coordinated Disclosure

When a report is received, the maintainer may:

1. Acknowledge receipt.
2. Reproduce and assess the reported behavior.
3. Determine affected versions and practical impact.
4. Coordinate with the reporter on additional technical information when necessary.
5. Develop and test a remediation.
6. Release a fix or mitigation when appropriate.
7. Publish a security advisory when disclosure is warranted.
8. Credit the reporter when requested and appropriate.

The current project policy targets an initial acknowledgment within **48 hours**. This is a response target rather than a guarantee that a complete investigation or remediation will be finished within that period.

Disclosure timing may depend on severity, exploitability, affected users, patch readiness, dependency coordination, and other practical factors.

---

## Security Advisories

Confirmed security issues may be documented using GitHub repository security advisories.

A public advisory may include:

* Affected versions.
* Fixed versions.
* Severity information.
* Security impact.
* Mitigation guidance.
* Upgrade guidance.
* Appropriate references and identifiers.
* Reporter credit, where applicable.

Sensitive exploit details should remain private until coordinated disclosure is appropriate.

---

## Scope

### In scope

Security vulnerabilities introduced by or materially enabled by this repository, including:

* `highrise_fast` runtime code.
* Packet parsing and validation.
* Serialization/deserialization.
* WebSocket connection management.
* Web API client behavior.
* CLI behavior.
* Request and task lifecycle handling.
* Credential or secret disclosure caused by the SDK.
* Security-sensitive configuration behavior.

### Generally out of scope

The following are normally outside this repository's direct security scope:

* Vulnerabilities in Highrise's servers or services.
* Highrise account enforcement decisions.
* Highrise platform policy disputes.
* Problems caused exclusively by a user's own bot application code.
* Problems caused exclusively by an unrelated third-party service.
* Generic package vulnerabilities that are entirely upstream and are not introduced or made exploitable by this project.
* Benchmark discrepancies that have no security consequence.
* Feature requests that do not represent a security vulnerability.

When in doubt, report the issue privately and let the maintainer determine whether it belongs in scope.

---

## Contact

Project:

`https://github.com/Tenslaster/highrise-bot-python`

Maintainer:

`Tenslaster`

Security reports should be handled through a **private GitHub security channel whenever available**. Do not place confidential vulnerability information in a public issue.

---

## Responsible Disclosure Statement

Thank you to security researchers and developers who responsibly identify problems and help improve the safety and reliability of this project.

The maintainer may recognize contributors in release notes or security advisories when appropriate and when the reporter agrees.

This security policy may be updated as the project, its supported versions, GitHub's security features, or its deployment practices evolve.
