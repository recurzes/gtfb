"""Domain sanitization utilities for GTFB blocklist rules."""

import re
from urllib.parse import urlparse

# A single hostname label: letters, digits and inner hyphens
_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def clean_domain_input(raw: str) -> str:
    """Sanitize a raw domain or URL string into a clean hostname.

    Strips protocol schemes (http://, https://), leading 'www.', path segments,
    query parameters, fragments, and leading/trailing whitespace. Normalizes the
    domain to lowercase.

    Args:
        raw: The raw input domain or URL string.

    Returns:
        Cleaned domain string, or empty string if input is blank or invalid.

    Examples:
        >>> clean_domain_input("  https://WWW.Reddit.com/r/all?sort=top  ")
        'reddit.com'
        >>> clean_domain_input("youtube.com/feed")
        'youtube.com'
        >>> clean_domain_input("  ")
        ''
    """
    if not isinstance(raw, str):
        return ""
    cleaned = raw.strip().lower()
    if not cleaned:
        return ""

    # Ensure a URL scheme is present so urllib.parse can properly extract the hostname
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", cleaned):
        cleaned = "http://" + cleaned

    try:
        parsed = urlparse(cleaned)
        domain = (parsed.hostname or "").strip()
        if not domain:
            # Fallback for unconventional inputs where hostname might be None
            netloc = parsed.netloc.split(":")[0].strip()
            path_host = parsed.path.split("/")[0].split(":")[0].strip()
            domain = netloc or path_host
    except Exception:
        domain = ""

    # Strip leading 'www.' if present
    if domain.startswith("www."):
        domain = domain[4:]

    domain = domain.strip()
    if not domain:
        return ""

    # Convert international names to ASCII (punycode), as required by browser block rules
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return ""

    if len(domain) > 253 or not all(_LABEL_RE.match(label) for label in domain.split(".")):
        return ""

    return domain
