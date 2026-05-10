import asyncio
from .stages import plain, robots, tls, vendor, ratelimit
from .report import build_recommendation
from .types import ReconReport

def run_pipeline(
    url: str,
    probe_rate: bool,
    concurrency: int,
    requests: int,
    impersonate: str,
    timeout: int,
    skip_tls: bool,
    skip_vendor: bool
) -> ReconReport:

    robots_res = robots.run(url, timeout)

    # Stage 1
    plain_res = plain.run(url, timeout)

    # Stage 2
    if skip_tls or plain_res.error:
        tls_res = None
    else:
        tls_res = tls.run(url, plain_res, impersonate, timeout)

    # Stage 3
    if skip_vendor:
        vendor_res = None
    else:
        vendor_res = vendor.run(plain_res, tls_res)
        
    # Stage 4
    if probe_rate and ((plain_res and not plain_res.error) or (tls_res and not tls_res.error)):
        rate_res = asyncio.run(ratelimit.run(
            url, True, requests, concurrency, plain_res, tls_res, impersonate
        ))
    else:
        rate_res = None
        
    rec = build_recommendation(plain_res, tls_res, vendor_res, rate_res, robots_res)
    
    return ReconReport(
        target=url,
        robots=robots_res,
        plain=plain_res,
        tls=tls_res,
        vendor=vendor_res,
        rate_limit=rate_res,
        recommendation=rec
    )
