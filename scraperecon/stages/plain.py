import time
import httpx
from ..types import PlainResult, Verdict
from ..utils import is_challenge_body

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; scraperecon/0.1)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

def get_verdict(status: int, body_preview: str = "") -> Verdict:
    if is_challenge_body(body_preview):
        return Verdict.BLOCKED
    if 200 <= status <= 299:
        return Verdict.OPEN
    elif status in (301, 302, 307, 308):
        return Verdict.REDIRECTED
    elif status in (403, 429, 503):
        return Verdict.BLOCKED
    else:
        return Verdict.UNCERTAIN

def run(url: str, timeout: int) -> PlainResult:
    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=DEFAULT_HEADERS)
        
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        headers = {k.lower(): v for k, v in resp.headers.items()}
        cookies = list(resp.cookies.keys())
        body_preview = resp.text[:2048]
        final_url = str(resp.url)
        
        # Check history to see if there was a redirect
        if resp.history:
            # We followed redirects, the final status is what matters for Open/Blocked/etc.
            # But the spec says "200-299 => OPEN, 301.. => REDIRECTED". If we follow redirects, 
            # we might just return the final status. Let's return the final status verdict.
            verdict = get_verdict(resp.status_code, body_preview)
        else:
            verdict = get_verdict(resp.status_code, body_preview)
            
        return PlainResult(
            verdict=verdict,
            status=resp.status_code,
            response_time_ms=response_time_ms,
            headers=headers,
            cookies=cookies,
            body_preview=body_preview,
            final_url=final_url
        )
    except Exception as e:
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        return PlainResult(
            verdict=Verdict.ERROR,
            status=None,
            response_time_ms=response_time_ms,
            headers={},
            cookies=[],
            body_preview="",
            final_url=url,
            error=str(e)
        )
