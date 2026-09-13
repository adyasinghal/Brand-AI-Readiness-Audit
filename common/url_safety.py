"""url_safety.py -- SSRF protection for every outbound fetch the audit makes
(initial URL, discovered links, sitemap URLs, redirect targets, browser
navigations). Applied before any request is issued, never after.

Policy (Round-3 handout, Priority 1 #2):
  - only http/https are ever fetched
  - credentials embedded in the URL (user:pass@host) are rejected
  - known cloud-metadata hosts/IPs are always rejected, even with allow_private
  - the hostname is resolved and EVERY returned address is checked -- a
    hostname that resolves to more than one IP is only safe if all of them are
  - by default (allow_private=False) loopback, private, link-local, multicast,
    unspecified, and reserved ranges are all rejected
  - DNS resolution failure is treated as unsafe (fail closed), not skipped

`allow_private=True` exists only so local test fixtures (a ThreadingHTTPServer
on 127.0.0.1) can be exercised; production callers (run_audit's default) never
set it.
"""
from __future__ import annotations
import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}

# Cloud metadata endpoints: blocked unconditionally, even with allow_private,
# because there is never a legitimate reason for a website audit to reach them.
_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.goog",
}
_BLOCKED_IPS = {
    "169.254.169.254",  # AWS/GCP/Azure/most clouds' instance-metadata address
    "fd00:ec2::254",     # AWS IMDS IPv6
}


@dataclass(frozen=True)
class UrlSafetyResult:
    safe: bool
    reason: Optional[str]  # None when safe


def _resolve(hostname: str):
    """Returns a list of ipaddress objects, or raises socket.gaierror."""
    infos = socket.getaddrinfo(hostname, None)
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def _ip_is_blocked(ip: "ipaddress._BaseAddress", allow_private: bool) -> Optional[str]:
    if str(ip) in _BLOCKED_IPS:
        return "cloud_metadata_address"
    if allow_private:
        return None
    if ip.is_loopback:
        return "loopback_address"
    if ip.is_link_local:
        return "link_local_address"
    if ip.is_multicast:
        return "multicast_address"
    if ip.is_unspecified:
        return "unspecified_address"
    if ip.is_private:
        return "private_address"
    if ip.is_reserved:
        return "reserved_address"
    return None


def classify_url(url: str, *, allow_private: bool = False) -> UrlSafetyResult:
    """The single choke point every outbound fetch must pass through first."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return UrlSafetyResult(False, "unparseable_url")

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return UrlSafetyResult(False, f"disallowed_scheme:{scheme or 'none'}")

    if parts.username or parts.password:
        return UrlSafetyResult(False, "credentials_in_url")

    hostname = parts.hostname
    if not hostname:
        return UrlSafetyResult(False, "no_hostname")

    hostname_lower = hostname.lower().rstrip(".")
    if hostname_lower in _BLOCKED_HOSTS:
        return UrlSafetyResult(False, "cloud_metadata_hostname")

    # A literal IP in the URL is checked directly; a DNS name is resolved and
    # every returned address is checked -- rebinding after the check would
    # still be caught because we connect to the address requests itself
    # resolves, but validating here rejects the common case up front.
    try:
        ips = _resolve(hostname_lower)
    except socket.gaierror:
        return UrlSafetyResult(False, "dns_resolution_failed")
    except Exception:
        return UrlSafetyResult(False, "dns_resolution_error")

    if not ips:
        return UrlSafetyResult(False, "dns_resolution_failed")

    for ip in ips:
        reason = _ip_is_blocked(ip, allow_private)
        if reason:
            return UrlSafetyResult(False, reason)

    return UrlSafetyResult(True, None)


def is_safe_url(url: str, *, allow_private: bool = False) -> bool:
    return classify_url(url, allow_private=allow_private).safe


def same_origin(url: str, origin: str) -> bool:
    a, b = urlsplit(url), urlsplit(origin)
    return (a.scheme.lower(), a.hostname and a.hostname.lower(), a.port) == \
           (b.scheme.lower(), b.hostname and b.hostname.lower(), b.port)
