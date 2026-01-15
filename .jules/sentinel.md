## 2025-01-26 - Critical SSRF in Webhook Client
**Vulnerability:** `send_to_discord_with_retry` accepted arbitrary URLs, allowing Server-Side Request Forgery (SSRF). A malicious user could probe internal services or cloud metadata services.
**Learning:** The validation function `validate_webhook_url` existed but was not called in the main sending function. Also, `validate_webhook_url` had a fallback lenient check that could be bypassed.
**Prevention:** Always enforce input validation at the point of use. Avoid "lenient" fallback checks for security-critical inputs like URLs.
