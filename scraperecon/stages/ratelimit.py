import asyncio
import time
from typing import Optional
from curl_cffi import requests
import httpx
from ..types import RateLimitResult, BlockType, PlainResult, TlsResult, Verdict
from .plain import DEFAULT_HEADERS

async def _worker(queue: asyncio.Queue, results: list, client, is_httpx: bool):
    while True:
        try:
            url = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        start_time = time.perf_counter()
        try:
            if is_httpx:
                resp = await client.get(url, headers=DEFAULT_HEADERS)
                status = resp.status_code
                retry_after = resp.headers.get("retry-after")
                is_redirect = status in (301, 302, 307, 308)
            else:
                resp = await client.get(url, headers=DEFAULT_HEADERS, allow_redirects=False)
                status = resp.status_code
                retry_after = resp.headers.get("retry-after")
                is_redirect = status in (301, 302, 307, 308)
                
            elapsed = int((time.perf_counter() - start_time) * 1000)
            
            is_soft_block = status in (429, 503) or is_redirect
            
            results.append({
                "status": status,
                "elapsed": elapsed,
                "is_soft_block": is_soft_block,
                "retry_after": retry_after
            })
        except Exception:
            elapsed = int((time.perf_counter() - start_time) * 1000)
            results.append({
                "status": 0,
                "elapsed": elapsed,
                "is_soft_block": False,
                "retry_after": None
            })
            
        queue.task_done()

async def run(
    url: str, 
    probe_rate: bool, 
    requests_count: int, 
    concurrency: int, 
    plain_result: PlainResult, 
    tls_result: Optional[TlsResult],
    profile: str
) -> Optional[RateLimitResult]:
    if not probe_rate:
        return None

    use_plain = False
    if tls_result is None or tls_result.verdict == Verdict.SKIPPED:
        use_plain = True

    queue = asyncio.Queue()
    for _ in range(requests_count):
        queue.put_nowait(url)

    results = []
    
    probe_start = time.perf_counter()
    
    if use_plain:
        async with httpx.AsyncClient(verify=False) as client:
            tasks = []
            for _ in range(concurrency):
                tasks.append(asyncio.create_task(_worker(queue, results, client, True)))
                await asyncio.sleep(0.1) # 100ms jitter
            await asyncio.gather(*tasks)
    else:
        async with requests.AsyncSession(impersonate=profile) as client:
            tasks = []
            for _ in range(concurrency):
                tasks.append(asyncio.create_task(_worker(queue, results, client, False)))
                await asyncio.sleep(0.1)
            await asyncio.gather(*tasks)

    probe_duration = time.perf_counter() - probe_start

    successful = sum(1 for r in results if 200 <= r["status"] < 300)
    blocked = sum(1 for r in results if r["status"] >= 400 or r["status"] == 0)
    
    block_type = None
    retry_after_secs = None
    
    for r in results:
        if r["status"] == 429:
            block_type = BlockType.RATE_LIMITED
            if r["retry_after"] and r["retry_after"].isdigit():
                retry_after_secs = int(r["retry_after"])
            break
            
    if not block_type:
        for r in results:
            if r["status"] == 403:
                block_type = BlockType.HARD_BLOCK
                break
                
    if not block_type:
        for r in results:
            if r["is_soft_block"] and r["status"] not in (429, 503):
                block_type = BlockType.SOFT_REDIRECT
                break
                
    times = sorted(r["elapsed"] for r in results)
    median_response_ms = times[len(times)//2] if times else 0

    if not block_type and len(results) >= 2:
        half = len(results) // 2
        first_half = sorted(r["elapsed"] for r in results[:half])
        second_half = sorted(r["elapsed"] for r in results[-half:])
        
        m1 = first_half[len(first_half)//2] if first_half else 0
        m2 = second_half[len(second_half)//2] if second_half else 0
        
        if m1 > 0 and m2 > m1 * 3:
            block_type = BlockType.SILENT

    avg_response_time_secs = (sum(r["elapsed"] for r in results) / len(results)) / 1000 if results else 1.0
    if avg_response_time_secs == 0:
        avg_response_time_secs = 0.001
        
    estimated_safe_rps = None
    if block_type and requests_count > 0:
        estimated_safe_rps = (successful / requests_count) * (concurrency / avg_response_time_secs)

    return RateLimitResult(
        total_requests=requests_count,
        successful=successful,
        blocked=blocked,
        block_type=block_type,
        estimated_safe_rps=estimated_safe_rps,
        retry_after_secs=retry_after_secs,
        median_response_ms=median_response_ms
    )
