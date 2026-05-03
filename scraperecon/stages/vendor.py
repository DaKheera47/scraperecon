from ..types import VendorResult, Confidence, PlainResult, TlsResult, Verdict
from ..signatures import load_signatures

def run(plain_result: PlainResult, tls_result: TlsResult | None) -> VendorResult:
    # Prefer Stage 2 result if it ran and was not skipped, else use Stage 1.
    if tls_result and tls_result.verdict not in (Verdict.SKIPPED, Verdict.ERROR):
        target_headers = tls_result.headers
        target_cookies = tls_result.cookies
        target_body = tls_result.body_preview
        target_status = tls_result.status
    else:
        target_headers = plain_result.headers
        target_cookies = plain_result.cookies
        target_body = plain_result.body_preview
        target_status = plain_result.status

    sigs = load_signatures()
    
    all_scores = []
    best_vendor = None
    best_score = 0.0
    best_signals = []
    
    target_body_lower = target_body.lower()
    target_cookies_lower = [c.lower() for c in target_cookies]
    
    for vendor_data in sigs.get("vendors", []):
        vendor_name = vendor_data["name"]
        signals = vendor_data.get("signals", [])
        
        max_possible = sum(s.get("weight", 0) for s in signals)
        if max_possible == 0:
            continue
            
        score = 0.0
        matched_signals = []
        
        for sig in signals:
            stype = sig["type"]
            weight = sig.get("weight", 0)
            matched = False
            match_str = ""
            
            if stype == "header_present":
                key = sig["key"].lower()
                if key in target_headers:
                    matched = True
                    match_str = f"{key} header"
            elif stype == "header_value":
                key = sig["key"].lower()
                val = sig["value"].lower()
                if key in target_headers and val in target_headers[key].lower():
                    matched = True
                    match_str = f"{val} in {key} header"
            elif stype == "cookie_name":
                val = sig["value"].lower()
                if val in target_cookies_lower:
                    matched = True
                    match_str = f"{sig['value']} cookie"
            elif stype == "body_contains":
                val = sig["value"].lower()
                if val in target_body_lower:
                    matched = True
                    match_str = f"{sig['value']} in body"
            elif stype == "status_code":
                if target_status == sig["value"]:
                    matched = True
                    match_str = f"status {sig['value']}"
                    
            if matched:
                score += weight
                matched_signals.append(match_str)
                
        normalized = score / max_possible
        all_scores.append((vendor_name, normalized))
        
        if normalized > best_score:
            best_score = normalized
            best_vendor = vendor_name
            best_signals = matched_signals

    if best_score >= 0.8:
        confidence = Confidence.HIGH
    elif best_score >= 0.5:
        confidence = Confidence.MEDIUM
    elif best_score >= 0.3:
        confidence = Confidence.LOW
    else:
        return VendorResult(
            vendor=None,
            confidence=None,
            matched_signals=[],
            all_scores=all_scores
        )
        
    return VendorResult(
        vendor=best_vendor,
        confidence=confidence,
        matched_signals=best_signals,
        all_scores=all_scores
    )
