from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from ..types import RobotsResult


def run(url: str, timeout: int) -> RobotsResult:
    robots_url = urljoin(url, "/robots.txt")

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(robots_url)

        if resp.status_code >= 400:
            return RobotsResult(blocked=False, robots_url=robots_url)

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(resp.text.splitlines())

        return RobotsResult(
            blocked=not parser.can_fetch("*", url),
            robots_url=robots_url,
        )
    except Exception as e:
        return RobotsResult(blocked=False, robots_url=robots_url, error=str(e))
