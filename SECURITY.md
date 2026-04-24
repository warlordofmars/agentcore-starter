# Security Policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use [GitHub's private vulnerability reporting](https://github.com/warlordofmars/hive/security/advisories/new) to submit a report confidentially. You'll receive a response within 5 business days.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested mitigations (optional)

## Disclosure policy

- We will acknowledge receipt within 5 business days
- We aim to release a fix within 30 days for high/critical issues
- We will credit reporters in the release notes unless you prefer to remain anonymous
- We ask that you give us reasonable time to address the issue before any public disclosure

## Scope

In scope:
- The hosted service at `hive.warlordofmars.net`
- Authentication and OAuth 2.1 implementation
- Memory data access controls
- API endpoints and data validation

Out of scope:
- Denial of service attacks
- Social engineering
- Issues in third-party dependencies (report those upstream; we track them via Dependabot and weekly Trivy scans)

## Supported versions

Only the latest deployed version of the hosted service receives security fixes.
