# Tenslaster Custom License

**Copyright © 2026 Tenslaster. All rights reserved.**

**Project:** `highrise-bot-python`
**Package:** `highrise-bot-python`
**Import:** `highrise_fast`
**License identifier:** `LicenseRef-Tenslaster-Custom`

---

## 1. Purpose

This license governs the use of the source code, documentation, and other original materials contained in the `highrise-bot-python` repository (collectively, the **"Software"**).

The Software is an **unofficial, independent implementation** of a Python SDK for Highrise bots.

The Software is not affiliated with, endorsed by, sponsored by, or officially supported by **Highrise** or **Pocket Worlds**.

Compatibility with the official Highrise Python SDK is an implementation and testing objective of this project and does not create any relationship of ownership, endorsement, partnership, or authorization.

---

## 2. Copyright Ownership

Except where expressly identified as third-party material, the original source code, documentation, test code, benchmark code, project-specific tooling, and other original materials authored for this repository are Copyright © 2026 Tenslaster.

All rights not expressly granted by this license are reserved.

Nothing in this license transfers ownership of the Software to any user, contributor, distributor, service provider, or other third party.

---

## 3. Limited License Grant

Subject to the terms of this license, Tenslaster grants you a limited, non-exclusive, non-transferable, revocable license to:

* access and download the Software from the official repository;
* install the Software for your own environment;
* execute and use the Software for development, testing, evaluation, and operation of Highrise bots;
* use the Software for personal, educational, research, internal, or commercial purposes, provided that the Software itself is not distributed, resold, sublicensed, or offered as a competing SDK;
* make private modifications to the Software for your own internal use.

This license permits use of the Software. It does **not** transfer ownership of the Software or grant unrestricted redistribution rights.

---

## 4. Distribution Restrictions

Without prior written permission from Tenslaster, you may **not**:

1. Redistribute the Software or substantial portions of its source code.
2. Publish a mirror, package, archive, bundle, fork, port, or repackaged distribution intended to substitute for or redistribute the Software.
3. Sell, rent, lease, sublicense, or otherwise commercially distribute the Software itself.
4. Publish modified versions of the Software for third-party download or installation.
5. Upload copies or modified copies of the Software to package indexes, software repositories, download services, app stores, or other distribution platforms.
6. Rebrand the Software and distribute it as your own SDK.
7. Remove or alter copyright, licensing, attribution, or proprietary notices.
8. Grant another person rights to the Software that exceed the rights granted to you under this license.
9. Use the Software's source code as the basis of a competing redistributed SDK without written permission.
10. Circumvent this license through automated mirroring, scraping, repackaging, or substantially equivalent redistribution.

Private internal copies and private internal modifications are permitted only to the extent expressly granted in Section 3.

---

## 5. Bot Applications

This license applies to the **Software itself** and does not automatically prohibit you from creating your own bot applications using the Software.

Your original bot code, configuration, assets, commands, databases, services, and other independently authored application materials remain your responsibility and, where applicable, remain subject to the licenses chosen by their respective authors.

You may develop and operate your own Highrise bots using the Software, including for commercial purposes, provided that you do not distribute the Software itself or a substantial copy of it as part of that distribution.

When a bot application is packaged or distributed in a way that would result in redistribution of the Software or a substantial portion of its source code, separate written permission from Tenslaster is required.

---

## 6. Private Modifications

You may modify the Software privately for your own development, testing, deployment, or internal operational requirements.

Private modifications:

* may be used internally without publication;
* remain subject to this license if they contain or substantially derive from the Software;
* must not be distributed publicly without prior written permission;
* must not be presented as an official Highrise or Pocket Worlds SDK.

Contributing a modification upstream through a pull request does not, by itself, change the license of the project.

Acceptance and licensing of contributions remain subject to the repository's contribution requirements and any separate contributor agreement applicable at the time.

---

## 7. Third-Party Software and Materials

The Software may depend on or interoperate with third-party software.

Third-party components are **not owned by Tenslaster merely because they are used by, imported by, or distributed separately from this project**, and they are not relicensed under this license unless their respective license expressly permits such treatment.

For the current project configuration, notable third-party dependencies include:

* `aiohttp`
* `orjson` (optional)

Development tooling may also include packages such as:

* `pytest`
* `pytest-asyncio`
* `pytest-cov`
* `ruff`
* `mypy`
* `build`
* `twine`

Each third-party package remains governed by its own applicable license, copyright notices, and terms.

Where third-party source code, notices, or licenses are included in the repository, those materials retain their original ownership and licensing terms.

Nothing in this license purports to relicense third-party software.

---

## 8. Highrise and Pocket Worlds Rights

**Highrise** and **Pocket Worlds** are names, brands, services, intellectual property, and/or trademarks belonging to their respective owners.

This license grants **no rights** to:

* Highrise trademarks;
* Pocket Worlds trademarks;
* Highrise logos;
* Pocket Worlds logos;
* Highrise service content;
* Highrise proprietary assets;
* Pocket Worlds proprietary assets;
* Highrise server-side code;
* Pocket Worlds server-side code;
* Highrise user-generated content;
* Pocket Worlds intellectual property generally.

This project is an independent implementation designed to communicate with publicly documented or observed Highrise bot interfaces. References to Highrise in the Software or its documentation are descriptive and do not imply endorsement, affiliation, partnership, or ownership.

Users remain responsible for complying with applicable Highrise terms, policies, developer requirements, and other platform rules when operating a bot.

---

## 9. No Warranty

THE SOFTWARE IS PROVIDED **"AS IS"** AND **"AS AVAILABLE"**, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW.

TO THE MAXIMUM EXTENT PERMITTED BY LAW, TENSLASTER DISCLAIMS ALL WARRANTIES, INCLUDING BUT NOT LIMITED TO:

* MERCHANTABILITY;
* FITNESS FOR A PARTICULAR PURPOSE;
* TITLE;
* NON-INFRINGEMENT;
* ACCURACY;
* RELIABILITY;
* AVAILABILITY;
* SECURITY;
* COMPATIBILITY;
* CONTINUOUS OR ERROR-FREE OPERATION.

THE SOFTWARE MAY CONTAIN BUGS, LIMITATIONS, INCOMPATIBILITIES, PERFORMANCE VARIATIONS, OR OTHER DEFECTS.

NO PERFORMANCE CLAIM, BENCHMARK, COMPATIBILITY TEST, OR DOCUMENTATION STATEMENT SHOULD BE INTERPRETED AS A WARRANTY OR GUARANTEE.

---

## 10. Highrise Compatibility Disclaimer

The Software attempts to provide a compatible development surface with the official Highrise Python SDK, including familiar bot handlers, request methods, protocol types, and Web API functionality.

Compatibility is tested against the official SDK used as the project's reference/oracle implementation, but:

* compatibility is not guaranteed across all Highrise service changes;
* undocumented Highrise behavior may change;
* private implementation details of the official SDK are not guaranteed to be reproduced;
* protocol behavior may change independently of this repository;
* a successful local compatibility test does not guarantee identical behavior in every live Highrise environment.

The official Highrise Python SDK remains a separate project maintained by Pocket Worlds.

---

## 11. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, TENSLASTER SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR FOR ANY LOSS OF DATA, PROFITS, REVENUE, BUSINESS, ACCOUNTS, CREDENTIALS, SERVICE AVAILABILITY, OR OTHER ECONOMIC OR NON-ECONOMIC LOSS ARISING OUT OF OR RELATED TO:

* THE SOFTWARE;
* USE OR INABILITY TO USE THE SOFTWARE;
* SOFTWARE DEFECTS;
* SECURITY INCIDENTS;
* HIGHRISE SERVICE CHANGES;
* THIRD-PARTY SERVICES;
* THIRD-PARTY DEPENDENCIES;
* BOT APPLICATION LOGIC;
* CONFIGURATION ERRORS;
* CREDENTIAL COMPROMISE;
* NETWORK FAILURES;
* SERVICE INTERRUPTIONS.

This limitation applies to the fullest extent permitted by applicable law.

---

## 12. Security Responsibilities

Users are responsible for operating their bots securely.

In particular, users are responsible for:

* protecting Highrise API tokens;
* keeping credentials out of source control;
* securing environment variables and secret files;
* controlling access to bot hosts;
* updating dependencies;
* reviewing logs for unintended secret disclosure;
* complying with Highrise policies and applicable law;
* validating and authorizing their own application-level actions;
* implementing application-specific rate limits and access controls when required.

The Software's validation, diagnostics, request cleanup, and transport safeguards do not replace application security.

Security vulnerabilities in this project should be reported privately according to [`SECURITY.md`](./SECURITY.md).

---

## 13. License Termination

This license automatically terminates if you materially violate its terms.

Upon termination, you must cease the activities no longer authorized by this license and, where legally required, remove distributed or accessible copies that you are not otherwise entitled to retain.

Termination does not affect rights that were lawfully acquired before termination where applicable law prevents retroactive cancellation of those rights.

Tenslaster may grant additional permissions in writing.

---

## 14. Permissions by Written Authorization

Tenslaster may, at its sole discretion, grant additional permissions beyond those stated in this license.

Any exception should be explicit and in writing.

A public discussion, issue comment, pull request, message, or informal statement should not be interpreted as a permanent amendment to this license unless Tenslaster clearly states that it is granting such permission.

---

## 15. No Implied Rights

No rights are granted by implication, estoppel, exhaustion, custom, or otherwise.

If a requested use is not expressly permitted by this license, permission must be obtained from Tenslaster before that use is undertaken.

---

## 16. Severability

If any provision of this license is determined to be unenforceable, invalid, or unlawful in a particular jurisdiction, that provision shall be interpreted or limited only to the minimum extent necessary, while the remaining provisions shall continue in effect to the fullest extent permitted by law.

---

## 17. Entire License

This document constitutes the license governing the Software unless a separate written agreement expressly supersedes or supplements it.

Nothing in this license changes the independent licenses of third-party dependencies.

---

## 18. Attribution

Copyright notices and license notices contained in the Software must not be removed or intentionally obscured.

The following attribution should remain associated with copies that are otherwise lawfully retained:

> `highrise-bot-python` — Copyright © 2026 Tenslaster.

---

## 19. Repository and Official References

Project repository:

`https://github.com/Tenslaster/highrise-bot-python`

Official Highrise Python SDK:

`https://github.com/pocketzworld/python-bot-sdk`

Highrise creator documentation:

`https://create.highrise.game/`

Official Highrise Python SDK package:

`https://pypi.org/project/highrise-bot-sdk/`

These references are provided for identification and compatibility context only. They do not alter the ownership or licensing terms of this Software.

---

## 20. License Summary

For convenience only, and not as a replacement for the full terms above:

| Action                                     | Permission |
| ------------------------------------------ | :--------: |
| Download the repository                    |      ✅     |
| Install the SDK for your own use           |      ✅     |
| Run the SDK                                |      ✅     |
| Build and operate Highrise bots with it    |      ✅     |
| Personal use                               |      ✅     |
| Educational use                            |      ✅     |
| Internal use                               |      ✅     |
| Commercial use of your own bot application |      ✅     |
| Make private modifications                 |      ✅     |
| Publicly redistribute the SDK              |      ❌     |
| Sell the SDK itself                        |      ❌     |
| Sublicense the SDK                         |      ❌     |
| Publish a modified SDK distribution        |      ❌     |
| Rebrand it as your own SDK                 |      ❌     |
| Remove copyright/license notices           |      ❌     |
| Grant downstream users broader SDK rights  |      ❌     |

This summary is informational only. **The operative terms are the full provisions of this license.**

---

**Copyright © 2026 Tenslaster. All rights reserved.**
