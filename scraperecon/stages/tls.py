import time
from curl_cffi import requests
from ..types import TlsResult, Verdict, PlainResult
from .plain import DEFAULT_HEADERS, get_verdict

def run(url: str, plain_result: PlainResult, profile: str, timeout: int) -> TlsResult:
    if plain_result.verdict == Verdict.OPEN:
        return TlsResult(
            verdict=Verdict.SKIPPED,
            status=None,
            response_time_ms=0,
            headers={},
            cookies=[],
            body_preview="",
            tls_was_blocker=False,
            profile_used=profile
        )
    
    start_time = time.perf_counter()
    try:
        resp = requests.get(
            url, 
            headers=DEFAULT_HEADERS, 
            impersonate=profile, 
            timeout=timeout, 
            allow_redirects=True
        )
        
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        headers = {k.lower(): v for k, v in resp.headers.items()}
        cookies = list(resp.cookies.keys())
        body_preview = resp.text[:2048]
        
        verdict = get_verdict(resp.status_code)
        
        tls_was_blocker = False
        if plain_result.verdict == Verdict.BLOCKED and verdict == Verdict.OPEN:
            tls_was_blocker = True
            
        return TlsResult(
            verdict=verdict,
            status=resp.status_code,
            response_time_ms=response_time_ms,
            headers=headers,
            cookies=cookies,
            body_preview=body_preview,
            tls_was_blocker=tls_was_blocker,
            profile_used=profile
        )
    except Exception as e:
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        return TlsResult(
            verdict=Verdict.ERROR,
            status=None,
            response_time_ms=response_time_ms,
            headers={},
            cookies=[],
            body_preview="",
            tls_was_blocker=False,
            profile_used=profile,
            error=str(e)
        )
