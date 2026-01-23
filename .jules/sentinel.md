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

## 2025-10-27 - GitHub Repo Traversal and Arbitrary File Write
**Vulnerability:** `update_github_cdn_urls` accepted `github_repo` strings like `user/repo/../../victim/target` and `file_path` strings like `../secret.txt`, allowing path traversal. This could enable an attacker to manipulate files in arbitrary repositories the user's token had access to.
**Learning:** Checking for the presence of a separator (like `/`) is not sufficient validation. Simple string concatenation for URL construction is dangerous when inputs can contain traversal sequences like `..`.
**Prevention:** Strictly validate structural inputs against a whitelist regex (e.g., `^[\w.-]+/[\w.-]+$`). Reject any input containing path traversal sequences (`..`) or unexpected characters before using them in API calls.

## 2026-01-20 - Resource Exhaustion via Unbounded Temporary Files
**Vulnerability:** The video node created temporary copies of videos (`discord_optimized_*`) to ensure Discord compatibility but failed to delete them. In long-running environments, this could fill the disk storage, leading to a Denial of Service (DoS).
**Learning:** Temporary files created for specific operations (like upload optimization) must be explicitly managed and cleaned up, regardless of success or failure of the operation. Relying on OS or application-level temp directory cleaning is insufficient for large media files.
**Prevention:** Use `try...finally` blocks to guarantee cleanup of temporary resources. Explicitly track created temporary artifacts and verify their deletion.

## 2026-01-23 - Symlink Overwrite in Custom Nodes
**Vulnerability:** Custom nodes (`DiscordSendSaveVideo`, `DiscordSendSaveImage`) overwrote existing files when `overwrite_last` was enabled. If the target file was a symlink, the overwrite followed the link, allowing arbitrary file overwrites.
**Learning:** Simply calculating an output path and opening it for writing is unsafe if the directory is shared or accessible by others. Tools like `subprocess.Popen` or libraries like `PIL.Image.save` will follow symlinks blindly.
**Prevention:** Explicitly check `os.path.islink(path)` before writing to any file path. Raise an error if a symlink is detected, especially in contexts where file overwrites are expected.
