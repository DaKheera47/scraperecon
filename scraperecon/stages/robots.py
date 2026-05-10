import gzip
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from ..types import RobotsResult

MAX_SITEMAPS = 100


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _sitemap_locations(text: str) -> list[str]:
    urls = []

    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() == "sitemap":
            sitemap_url = value.strip()
            if sitemap_url:
                urls.append(sitemap_url)

    return urls


def _xml_text(resp: httpx.Response) -> str:
    content = resp.content
    if str(resp.url).endswith(".gz") or content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)

    return content.decode(resp.encoding or "utf-8", errors="replace")


def _child_text(element: ET.Element, child_name: str) -> str:
    for child in element:
        if _local_name(child.tag) == child_name and child.text:
            return child.text.strip()

    return ""


def _count_sitemap_urls(
    client: httpx.Client,
    sitemap_urls: list[str],
) -> tuple[int, int, list[str]]:
    seen_sitemaps = set()
    seen_urls = set()
    queue = list(dict.fromkeys(sitemap_urls))

    while queue and len(seen_sitemaps) < MAX_SITEMAPS:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue

        seen_sitemaps.add(sitemap_url)

        try:
            resp = client.get(sitemap_url)
            if resp.status_code >= 400:
                continue

            root = ET.fromstring(_xml_text(resp))
        except (ET.ParseError, OSError, httpx.HTTPError):
            continue

        for element in root:
            tag_name = _local_name(element.tag)
            child_url = _child_text(element, "loc")
            if not child_url:
                continue

            if tag_name == "sitemap" and child_url not in seen_sitemaps:
                queue.append(child_url)
            elif tag_name == "url":
                seen_urls.add(child_url)

    return len(seen_urls), len(seen_sitemaps), sorted(seen_sitemaps)


def run(url: str, timeout: int) -> RobotsResult:
    robots_url = urljoin(url, "/robots.txt")

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(robots_url)

            sitemap_urls = []
            if resp.status_code < 400:
                sitemap_urls = _sitemap_locations(resp.text)
                if not sitemap_urls:
                    sitemap_urls = [urljoin(url, "/sitemap.xml")]

                parser = RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(resp.text.splitlines())
                blocked = not parser.can_fetch("*", url)
            else:
                blocked = False
                sitemap_urls = [urljoin(url, "/sitemap.xml")]

            sitemap_url_count, sitemaps_checked, sitemap_sources = _count_sitemap_urls(
                client,
                sitemap_urls,
            )

        return RobotsResult(
            blocked=blocked,
            robots_url=robots_url,
            sitemap_url_count=sitemap_url_count,
            sitemaps_checked=sitemaps_checked,
            sitemap_sources=sitemap_sources,
        )
    except Exception as e:
        return RobotsResult(blocked=False, robots_url=robots_url, error=str(e))
