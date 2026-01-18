## 2025-01-26 - Critical SSRF in Webhook Client
**Vulnerability:** `send_to_discord_with_retry` accepted arbitrary URLs, allowing Server-Side Request Forgery (SSRF). A malicious user could probe internal services or cloud metadata services.
**Learning:** The validation function `validate_webhook_url` existed but was not called in the main sending function. Also, `validate_webhook_url` had a fallback lenient check that could be bypassed.
**Prevention:** Always enforce input validation at the point of use. Avoid "lenient" fallback checks for security-critical inputs like URLs.

## 2025-02-14 - Token Leakage in Exception Logs
**Vulnerability:** `requests` exceptions include the full URL in their string representation. When logging `e` or `str(e)`, the Discord webhook token (embedded in the URL) was written to logs in plain text.
**Learning:** Exception messages from third-party libraries may contain sensitive data found in arguments (like URLs with tokens). `str(e)` is not safe to log directly if the exception originated from a sensitive operation.
**Prevention:** Sanitize exception messages before logging. Specifically, use regex to scrub known sensitive patterns (like webhook tokens) from exception strings. When re-raising or wrapping exceptions, ensure the sanitized message is used but context (like `response` objects) is preserved.

## 2025-02-21 - Token Leakage in Upstream API Error Responses
**Vulnerability:** Upstream APIs (like GitHub) may echo back sensitive request headers or credentials in their error response bodies (e.g., "Bad credentials: [TOKEN] is invalid"). Including raw `response.text` in application error messages or logs leaked these credentials.
**Learning:** Never assume external API error responses are safe to log or display. They may contain sensitive data sent in the request (headers, body) or specific to the failure context.
**Prevention:** Sanitize raw response bodies (`response.text`) before including them in error logs or exception messages. Scrub known sensitive patterns (like API tokens) from any external input before outputting it.
