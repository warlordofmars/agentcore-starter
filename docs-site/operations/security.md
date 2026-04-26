# Security and secrets

This page documents the operational secret contracts that AgentCore Starter
relies on at runtime: which environment variables and SSM parameters
they map to, which file in the codebase consumes them, how to rotate
them safely, and what the startup-time fail-closed posture looks like.

All SSM parameters use a per-environment path so non-prod and prod never
share secrets:

```text
prod   → /agentcore-starter/<name>
others → /agentcore-starter/<env_name>/<name>
```

The CDK stack in `infra/stacks/starter_stack.py` provisions most
secret parameters with a `CHANGE_ME_ON_FIRST_DEPLOY` placeholder and
applies `RemovalPolicy.RETAIN` so a stack delete never destroys the
live secret material. The `AllowedEmails` parameter is the exception:
it ships with `"[]"` (deny-all) by default so a freshly-deployed
stack never grants management access to anyone until the deployer
explicitly populates the list.

> **Fail-closed startup validation is tracked under
> [issue #16](https://github.com/warlordofmars/agentcore-starter/issues/16).**
> Today, several of the contracts below tolerate the
> `CHANGE_ME_ON_FIRST_DEPLOY` placeholder by silently degrading
> behaviour (origin-verify is the clearest example). Once #16 lands,
> the application will refuse to start when any required secret is
> still unrotated. Sections below call out both the **current**
> behaviour and the **post-#16** behaviour where they differ.

## Origin verification (CloudFront → Lambda)

In prod, CloudFront injects a shared secret on every request to the
Lambda Function URL via the `X-Origin-Verify` header. When that
header injection is enabled, the Lambda middleware rejects requests
that do not present the expected value, so the public Function URL
cannot be hit directly to bypass CloudFront's WAF,
geo-restrictions, and CSP headers.

| Field | Value |
| --- | --- |
| Env var (override) | `STARTER_ORIGIN_VERIFY_SECRET` |
| Env var (SSM path) | `STARTER_ORIGIN_VERIFY_PARAM` |
| SSM parameter path | `/agentcore-starter/origin-verify-secret` (prod) or `/agentcore-starter/<env_name>/origin-verify-secret` |
| Header name | `X-Origin-Verify` |
| Consumer (Lambda) | `src/starter/auth/tokens.py` (`_origin_verify_secret()`) |
| Consumer (middleware) | `src/starter/api/main.py` (`_verify_origin_secret`) |
| Injector (CloudFront) | `infra/stacks/starter_stack.py` (`origin_verify_header`, prod-only) |

### Current behaviour

The middleware actively verifies the header only when **both** of the
following are true:

1. `STARTER_ORIGIN_VERIFY_PARAM` (or `STARTER_ORIGIN_VERIFY_SECRET`)
   is set in the Lambda environment.
2. The resolved value is **not** the literal placeholder
   `CHANGE_ME_ON_FIRST_DEPLOY`.

When those conditions are met, the request is rejected if the incoming
`x-origin-verify` header does **not** match the resolved value. A
matching header is the success case and the request is allowed through.

The CDK stack sets `STARTER_ORIGIN_VERIFY_PARAM` in **every**
environment, but CloudFront only injects the `X-Origin-Verify`
header on the prod distribution. In non-prod environments the
middleware is effectively skipping enforcement only because the SSM
parameter still holds the `CHANGE_ME_ON_FIRST_DEPLOY` placeholder
(condition 2 above) — **do not rotate the non-prod parameter away
from the placeholder unless you also wire CloudFront header injection
for that environment**, or non-prod traffic will start being rejected.
In prod, if the SSM parameter still holds the placeholder, the
middleware silently allows every request through. **Rotate the
secret immediately after the first prod deploy** (procedure below).
Issue #16 will turn this silent-pass into a startup error.

The current resolver in `src/starter/auth/tokens.py`
(`_origin_verify_secret`) also returns `None` on any SSM exception
(missing parameter, IAM denial, network error). When `None` is
returned, the middleware fails the first condition of its check and
allows the request through. Because `_origin_verify_secret()` is
wrapped in `functools.lru_cache(maxsize=1)`, this fail-open state
only happens for a given Lambda execution environment if its first
secret read hits that exception path and caches `None`; if the secret
was already read successfully, later transient SSM outages do not
disable enforcement for that warm process. Issue #16 will replace
this fail-open behaviour with a startup-time failure when the
parameter is configured but cannot be read.

### Rotation procedure

1. Generate a new high-entropy value (e.g. `openssl rand -hex 32`).
2. Update the SSM parameter:
   ```bash
   aws ssm put-parameter \
     --name /agentcore-starter/origin-verify-secret \
     --value "$NEW_SECRET" --type String --overwrite
   ```
3. Re-deploy the stack so CloudFront picks up the new value via the
   `CfnDynamicReference` in `origin_verify_header`. CDK only resolves
   the SSM dynamic reference at synth/deploy time, so a parameter
   update alone is not enough.
4. Bounce the Lambda (e.g. publish a new version or update an
   environment variable) so the `lru_cache` on `_origin_verify_secret`
   re-reads SSM. CloudFront and Lambda are briefly out of sync during
   this window — schedule rotations during low traffic.

## JWT signing secret

Every JWT issued by the application — today, the management session
tokens; once you add OAuth 2.1 token issuance, the bearer access
tokens too — is signed with HS256 using a single shared secret
stored in SSM. The template ships only the OAuth 2.1 discovery
documents (`/.well-known/oauth-authorization-server` and
`/.well-known/oauth-protected-resource`); the
`/oauth/authorize` and `/oauth/token` endpoints are not implemented
yet.

| Field | Value |
| --- | --- |
| Env var (override) | `STARTER_JWT_SECRET` |
| Env var (SSM path) | `STARTER_JWT_SECRET_PARAM` |
| SSM parameter path | `/agentcore-starter/jwt-secret` (prod) or `/agentcore-starter/<env_name>/jwt-secret` |
| Algorithm | HS256 (symmetric) |
| Issuer claim (`iss`) | `https://<custom_domain>` (set via `STARTER_ISSUER`) |
| Consumer | `src/starter/auth/tokens.py` (`_jwt_secret()`, `decode_jwt`, `decode_mgmt_jwt`) |

### Current behaviour

`_jwt_secret()` resolves the secret in this order:

1. `STARTER_JWT_SECRET` env var (used by tests and local dev).
2. SSM `STARTER_JWT_SECRET_PARAM` (Lambda runtime).
3. A random 32-byte fallback generated per process — intended as a
   **local-dev escape hatch**, but `_jwt_secret()` also takes this
   branch on **any** SSM exception (missing parameter, IAM denial,
   network error). In Lambda this means tokens issued by one cold
   start will not validate on the next, silently invalidating every
   client session.

The fallback is what makes a half-configured deploy dangerous: if
SSM is unreachable or the parameter is missing, every cold start
issues a new secret and previously-issued tokens silently stop
validating. Issue #16 will replace the fallback with a hard startup
error in deployed environments.

### Rotation procedure

Rotating the JWT secret invalidates **every** outstanding token —
both API access tokens and active management UI sessions. Plan
accordingly.

1. Generate a new value: `openssl rand -hex 32`.
2. Update SSM:
   ```bash
   aws ssm put-parameter \
     --name /agentcore-starter/jwt-secret \
     --value "$NEW_SECRET" --type String --overwrite
   ```
3. Force a Lambda cold start so `lru_cache` re-reads (publish a new
   version or touch an env var).
4. All clients — including the management UI — must re-authenticate.

## Google OAuth

The management UI authenticates human users via Google OAuth 2.0.
Only emails on the allowlist are admitted, and the same allowlist
doubles as the admin-role grant list.

| Field | Value |
| --- | --- |
| Client ID env var | `GOOGLE_CLIENT_ID` |
| Client ID SSM env var | `GOOGLE_CLIENT_ID_PARAM` |
| Client ID SSM path | `/agentcore-starter/google-client-id` (prod) or `/agentcore-starter/<env_name>/google-client-id` |
| Client secret env var | `GOOGLE_CLIENT_SECRET` |
| Client secret SSM env var | `GOOGLE_CLIENT_SECRET_PARAM` |
| Client secret SSM path | `/agentcore-starter/google-client-secret` (prod) or `/agentcore-starter/<env_name>/google-client-secret` |
| Allowlist env var | `ALLOWED_EMAILS` (JSON array literal) |
| Allowlist SSM env var | `ALLOWED_EMAILS_PARAM` |
| Allowlist SSM path | `/agentcore-starter/allowed-emails` (prod) or `/agentcore-starter/<env_name>/allowed-emails` |
| Allowlist default | `"[]"` — empty list, denies all |
| Redirect URI | `https://<custom_domain>/auth/callback` |
| Consumer | `src/starter/auth/google.py`; login flow in `src/starter/auth/mgmt_auth.py` |

### Current behaviour

- The client ID and secret cache on first read
  (`functools.lru_cache`); changing them in SSM requires a Lambda
  bounce.
- The allowlist is wrapped in a 60-second TTL cache so operators can
  add or remove emails without forcing a cold start.
- `_allowed_emails()` **fails closed** on parse or load errors: a
  malformed JSON value or an unreachable SSM call is logged and
  treated as an empty list. No login is admitted.
- An empty allowlist (`"[]"` — the default after first deploy) means
  every login attempt is rejected with HTTP 403, including the
  deployer's own. Populate the parameter before expecting anyone to
  log in.
- Admin role is granted by the `is_admin_email` heuristic in
  `src/starter/auth/google.py`, which today maps to membership in
  the same allowlist — every allowlisted email is an admin. Replace
  this if you need a more granular role split.

### Redirect URI registration

The redirect URI registered in the Google Cloud Console must match
the application's issuer exactly. The issuer is computed as
`https://<custom_domain>` from the CDK stack, where `custom_domain`
is `agentcore-starter.<HOSTED_ZONE_NAME>` in prod or
`agentcore-starter-<env_name>.<HOSTED_ZONE_NAME>` otherwise.

### Rotation procedure

**Client secret rotation** (low-impact — sessions persist):

1. In the Google Cloud Console, generate a new client secret and
   keep the old one active until cut-over completes.
2. Update SSM:
   ```bash
   aws ssm put-parameter \
     --name /agentcore-starter/google-client-secret \
     --value "$NEW_SECRET" --type String --overwrite
   ```
3. Bounce the Lambda so the `lru_cache` re-reads.
4. Once new logins succeed, delete the old secret in the console.

**Allowlist update** (no cold start needed):

```bash
aws ssm put-parameter \
  --name /agentcore-starter/allowed-emails \
  --value '["alice@example.com","bob@example.com"]' \
  --type String --overwrite
```

The change is picked up within 60 seconds (TTL cache).

**Client ID rotation** is rare and effectively a re-registration —
treat it as a new OAuth setup: update SSM, bounce the Lambda, and
update the redirect URI in the Google Cloud Console if it changed.

## Management JWT contract

The management UI stores a short-lived signed JWT in browser
`localStorage` and presents it as a `Bearer` token on every API
call. The token is self-contained — no DynamoDB lookup at validation
time — so a stolen token is valid until its `exp` passes.

| Field | Value |
| --- | --- |
| Algorithm | HS256 (signed with the JWT signing secret above) |
| Issuer (`iss`) | matches `STARTER_ISSUER` |
| Subject (`sub`) | user's email |
| `email` claim | user's email |
| `display_name` claim | from Google ID token (`name`) |
| `role` claim | `"admin"` or `"user"` (set at login from `is_admin_email`) |
| `typ` claim | `"mgmt"` (distinguishes from API access tokens) |
| `iat` / `exp` claims | seconds since epoch; TTL = 8 hours |
| TTL constant | `MGMT_JWT_TTL_SECONDS = 28800` in `src/starter/auth/tokens.py` |
| Browser storage key | `localStorage["starter_mgmt_token"]` |
| Issuer (server) | `src/starter/auth/tokens.py` (`issue_mgmt_jwt`) via `src/starter/auth/mgmt_auth.py` |
| Validator (server) | `src/starter/auth/tokens.py` (`decode_mgmt_jwt`) via `src/starter/api/_auth.py` (`require_mgmt_user`, `require_admin`) |
| Issuer (UI) | server-side `mgmt_callback` returns an HTML redirect that writes the token |
| Sender (UI) | `ui/src/api.js` reads the token and sets the `Authorization` header |

### Validation rules

`decode_mgmt_jwt` enforces, in order:

1. Signature verifies under the active JWT signing secret.
2. `iss` claim equals `STARTER_ISSUER`.
3. `exp` claim is in the future.
4. `typ` claim equals `"mgmt"` — an OAuth 2.1 access token cannot be
   replayed as a management session, and vice versa.

Failures raise `JWTError`, which `require_mgmt_user` translates to
HTTP 401. `require_admin` adds an HTTP 403 if `role != "admin"`.

The UI clears `localStorage["starter_mgmt_token"]` on any 401 from
the API; see `ui/src/api.js`.

### Rotation procedure

Management JWTs are session credentials, not long-lived secrets —
"rotation" means either waiting out the 8-hour TTL or invalidating
all outstanding tokens by rotating the signing secret (see the
[JWT signing secret](#jwt-signing-secret) section). There is no
revocation list for individual mgmt tokens; remove a user by
removing their email from `ALLOWED_EMAILS` so they cannot log in
again, and either rotate the signing secret or wait for `exp`.

## Rotation quick reference

Summary of all secret rotations covered above, in roughly increasing
order of operational impact:

| Secret | Impact | Cold start required | TTL pickup |
| --- | --- | --- | --- |
| `ALLOWED_EMAILS` | Adds/removes a user; takes effect within 60s | No | 60 seconds (allowlist cache) |
| Origin-verify secret | Brief CloudFront/Lambda mismatch window | Yes (Lambda) + redeploy (CloudFront) | Immediate after redeploy |
| Google client secret | Logged-in sessions persist; new logins use new secret | Yes (Lambda) | Immediate after cold start |
| Google client ID | Effectively a re-registration | Yes (Lambda) | Immediate after cold start |
| JWT signing secret | **All outstanding tokens invalidated** (API + UI sessions) | Yes (Lambda) | Immediate after cold start |

General playbook for any SSM-backed secret:

1. Generate a new value (e.g. `openssl rand -hex 32`).
2. `aws ssm put-parameter --name <path> --value "$NEW" --type String --overwrite`.
3. For CloudFront-injected values (origin-verify), redeploy the CDK
   stack so the dynamic reference re-resolves.
4. Force a Lambda cold start (publish a new version, or touch an
   environment variable) so `functools.lru_cache` discards the old
   value.
5. Verify the new value is in effect: hit the API with a fresh token,
   confirm 200; for origin-verify, confirm a direct Function URL
   request without the header is rejected. The basic header check
   already enforces today once the secret is rotated away from the
   placeholder; #16 only changes the placeholder/SSM-error
   fail-closed behaviour.

### Future fail-closed validation (#16)

After [issue #16](https://github.com/warlordofmars/agentcore-starter/issues/16)
lands, the Lambda will refuse to start when any of the SSM-backed
secrets above still hold the `CHANGE_ME_ON_FIRST_DEPLOY` placeholder.
The startup-time check will run before the FastAPI app accepts any
request, so a half-configured deploy fails the health check rather
than degrading silently. Until then, treat the placeholder values
as a "first-deploy task" — rotate every SSM parameter with placeholder
content immediately after the initial CDK deploy.
