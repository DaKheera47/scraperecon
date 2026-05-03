from typing import Optional
from .types import Recommendation, ReconReport, PlainResult, TlsResult, VendorResult, RateLimitResult, Verdict, BlockType

def build_recommendation(
    plain: PlainResult,
    tls: Optional[TlsResult],
    vendor: Optional[VendorResult],
    rate: Optional[RateLimitResult]
) -> Recommendation:
    
    use_tls_impersonation = False
    profile = None
    captcha_detected = False
    proxy_recommended = False
    notes = []
    
    if plain.verdict == Verdict.OPEN:
        use_tls_impersonation = False
    elif tls and tls.tls_was_blocker:
        use_tls_impersonation = True
        profile = tls.profile_used
    elif plain.verdict in (Verdict.BLOCKED, Verdict.CHALLENGED) and tls and tls.verdict in (Verdict.BLOCKED, Verdict.CHALLENGED):
        use_tls_impersonation = True
        notes.append("Both stages blocked/challenged: may need browser automation (Playwright + stealth)")
        
    if vendor and vendor.vendor == "Cloudflare":
        notes.append("Cloudflare detected: consider Playwright + stealth plugin if curl_cffi fails")
        
    if rate and rate.block_type is not None:
        proxy_recommended = True
        
    body_to_check = ""
    if tls and tls.verdict not in (Verdict.SKIPPED, Verdict.ERROR):
        body_to_check = tls.body_preview.lower()
    else:
        body_to_check = plain.body_preview.lower()
        
    if "captcha" in body_to_check or "challenge" in body_to_check:
        captcha_detected = True
        
    return Recommendation(
        use_tls_impersonation=use_tls_impersonation,
        profile=profile,
        captcha_detected=captcha_detected,
        proxy_recommended=proxy_recommended,
        notes=notes
    )
