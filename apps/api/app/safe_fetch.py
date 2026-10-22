"""
Server-side fetching of user-supplied URLs without SSRF.

- only http/https, no credentials in the URL
- every address the host resolves to must be public (no loopback, private, link-local, metadata, ...)
- the connection is pinned to the validated IP (Host header + TLS SNI keep the original name), so a
  second DNS answer cannot redirect the request to an internal address
- redirects are followed manually and every hop is validated again
- the body is streamed and aborted as soon as it exceeds `max_bytes`
"""
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.config import settings

MAX_REDIRECTS = 3
USER_AGENT = "HotCrowdMediaFetcher/1.0"


class FetchError(Exception):
    """The URL was rejected or could not be fetched safely."""


@dataclass
class Fetched:
    content: bytes
    content_type: str
    final_url: str


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_unspecified)


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError("Could not resolve the host.") from exc
    return sorted({info[4][0] for info in infos})


def _pinned_target(scheme: str, ip: str, port: int, path_and_query: str) -> str:
    host = f"[{ip}]" if ":" in ip else ip
    return f"{scheme}://{host}:{port}{path_and_query}"


def fetch_public(
    url: str,
    *,
    max_bytes: int,
    timeout: float = 15.0,
    transport: httpx.BaseTransport | None = None,
) -> Fetched:
    current = url.strip()
    for _hop in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise FetchError("Only http(s) URLs are allowed.")
        if parts.username or parts.password:
            raise FetchError("URLs with credentials are not allowed.")
        try:
            port = parts.port or (443 if parts.scheme == "https" else 80)
        except ValueError as exc:
            raise FetchError("Invalid port.") from exc
        host = parts.hostname

        addresses = _resolve(host, port)
        if not addresses:
            raise FetchError("Could not resolve the host.")
        if not settings.allow_private_fetch and not all(_is_public(a) for a in addresses):
            raise FetchError("That address is not allowed.")

        path = parts.path or "/"
        target = _pinned_target(parts.scheme, addresses[0], port, path + (f"?{parts.query}" if parts.query else ""))
        default_port = 443 if parts.scheme == "https" else 80
        host_header = host if port == default_port else f"{host}:{port}"
        headers = {"Host": host_header, "User-Agent": USER_AGENT, "Accept": "*/*"}
        extensions = {"sni_hostname": host} if parts.scheme == "https" else {}

        with httpx.Client(transport=transport, timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", target, headers=headers, extensions=extensions) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("Redirect without a location.")
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise FetchError(f"The server answered {response.status_code}.")
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise FetchError("The file is too large.")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise FetchError("The file is too large.")
                    chunks.append(chunk)
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                return Fetched(b"".join(chunks), content_type, current)
    raise FetchError("Too many redirects.")
