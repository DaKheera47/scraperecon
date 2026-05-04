import json
import dataclasses
from enum import Enum
import typer
from rich.console import Console
from rich.text import Text
from .pipeline import run_pipeline
from .types import ReconReport, Verdict, Confidence

app = typer.Typer(add_completion=False)
SUPPORTED_IMPERSONATION_PROFILES = (
    "chrome131",
    "chrome120",
    "safari170",
)

def validate_impersonation_profile(value: str) -> str:
    if value not in SUPPORTED_IMPERSONATION_PROFILES:
        choices = ", ".join(SUPPORTED_IMPERSONATION_PROFILES)
        raise typer.BadParameter(
            f"Unsupported TLS profile '{value}'. Choose one of: {choices}."
        )
    return value

def _default_json(obj):
    if isinstance(obj, Enum):
        return obj.value
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def format_verdict(verdict: Verdict) -> Text:
    if verdict == Verdict.OPEN:
        return Text("Open", style="bold green")
    elif verdict == Verdict.BLOCKED:
        return Text("Blocked", style="bold red")
    elif verdict == Verdict.CHALLENGED:
        return Text("Challenged", style="bold magenta")
    elif verdict in (Verdict.UNCERTAIN, Verdict.SKIPPED):
        return Text(verdict.value, style="bold yellow")
    elif verdict == Verdict.ERROR:
        return Text("Error", style="bold red")
    else:
        return Text(verdict.value, style="bold")

def print_human(report: ReconReport):
    console = Console()
    err_console = Console(stderr=True)
    
    console.print(f"[bold]scraperecon v0.1.0[/bold] — {report.target}")
    console.print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    console.print()
    
    # Stage 1
    console.print("[bold]Stage 1 — Plain HTTP (httpx, scraper User-Agent)[/bold]")
    if report.plain.error:
        err_console.print(f"  [red]Error:[/red] {report.plain.error}")
        console.print("  Verdict:  ", format_verdict(report.plain.verdict))
    else:
        console.print(f"  Status:   {report.plain.status}")
        console.print(f"  Time:     {report.plain.response_time_ms}ms")
        console.print("  Verdict:  ", format_verdict(report.plain.verdict))
    console.print()
    
    # Stage 2
    if report.tls:
        console.print(f"[bold]Stage 2 — TLS Impersonation ({report.tls.profile_used})[/bold]")
        if report.tls.error:
            err_console.print(f"  [red]Error:[/red] {report.tls.error}")
            console.print("  Verdict:  ", format_verdict(report.tls.verdict))
        elif report.tls.verdict == Verdict.SKIPPED:
            console.print("  [yellow]Skipped (Stage 1 was Open)[/yellow]")
        else:
            console.print(f"  Status:   {report.tls.status}")
            console.print(f"  Time:     {report.tls.response_time_ms}ms")
            console.print("  Verdict:  ", format_verdict(report.tls.verdict))
            if report.tls.tls_was_blocker:
                console.print("  Note:     [green]TLS fingerprint was the blocker ✓[/green]")
    else:
        console.print("[bold]Stage 2 — TLS Impersonation[/bold]")
        console.print("  [yellow]Skipped[/yellow]")
    console.print()
    
    # Stage 3
    console.print("[bold]Stage 3 — Vendor Detection[/bold]")
    if report.vendor:
        if report.vendor.vendor:
            console.print(f"  Vendor:     [bold]{report.vendor.vendor}[/bold]")
            console.print(f"  Confidence: {report.vendor.confidence.value}")
            console.print(f"  Signals:    {', '.join(report.vendor.matched_signals)}")
        else:
            console.print("  [dim]No known vendor detected[/dim]")
    else:
        console.print("  [yellow]Skipped[/yellow]")
    console.print()
    
    # Stage 4
    console.print("[bold]Stage 4 — Rate Limit Probe[/bold]")
    if report.rate_limit:
        console.print(f"  Requests:   {report.rate_limit.successful} successful, {report.rate_limit.blocked} blocked (out of {report.rate_limit.total_requests})")
        console.print(f"  Median ms:  {report.rate_limit.median_response_ms}ms")
        if report.rate_limit.block_type:
            console.print(f"  Block Type: [bold red]{report.rate_limit.block_type.value}[/bold red]")
            if report.rate_limit.estimated_safe_rps:
                console.print(f"  Est. Safe:  ~{report.rate_limit.estimated_safe_rps:.1f} req/s")
        else:
            console.print("  [green]No rate limit detected at this volume[/green]")
    else:
        console.print("  [yellow]Skipped (pass --probe-rate to enable)[/yellow]")
    console.print()
    
    # Recommendations
    console.print("[bold]Recommendation[/bold]")
    rec = report.recommendation
    if rec.use_tls_impersonation:
        console.print(f"  [green]Use curl_cffi with {rec.profile or 'appropriate'} TLS profile[/green]")
    else:
        console.print("  [green]Plain HTTP (httpx/requests) should be sufficient[/green]")
        
    if rec.captcha_detected:
        console.print("  [red]CAPTCHA/Challenge detected[/red]")
    else:
        console.print("  No CAPTCHA detected")
        
    if rec.proxy_recommended:
        console.print("  [yellow]Proxy rotation recommended due to rate limits[/yellow]")
    else:
        console.print("  Proxy rotation not strictly required at tested volume")
        
    for note in rec.notes:
        console.print(f"  Note: {note}")

def print_json(report: ReconReport):
    # Map to the requested JSON format
    out = {
        "target": report.target,
        "stages": {
            "plain": None,
            "tls": None,
            "vendor": None,
            "rate_limit": None
        },
        "recommendation": dataclasses.asdict(report.recommendation)
    }
    
    if report.plain:
        out["stages"]["plain"] = {
            "verdict": report.plain.verdict.value,
            "status": report.plain.status,
            "response_time_ms": report.plain.response_time_ms
        }
        if report.plain.error:
            out["stages"]["plain"]["error"] = report.plain.error
            
    if report.tls:
        out["stages"]["tls"] = {
            "verdict": report.tls.verdict.value,
            "status": report.tls.status,
            "response_time_ms": report.tls.response_time_ms,
            "tls_was_blocker": report.tls.tls_was_blocker,
            "profile": report.tls.profile_used
        }
        if report.tls.error:
            out["stages"]["tls"]["error"] = report.tls.error
            
    if report.vendor and report.vendor.vendor:
        out["stages"]["vendor"] = {
            "vendor": report.vendor.vendor,
            "confidence": report.vendor.confidence.value if report.vendor.confidence else None,
            "matched_signals": report.vendor.matched_signals
        }
        
    if report.rate_limit:
        out["stages"]["rate_limit"] = {
            "total_requests": report.rate_limit.total_requests,
            "successful": report.rate_limit.successful,
            "blocked": report.rate_limit.blocked,
            "block_type": report.rate_limit.block_type.value if report.rate_limit.block_type else None,
            "estimated_safe_rps": report.rate_limit.estimated_safe_rps,
            "retry_after_secs": report.rate_limit.retry_after_secs,
            "median_response_ms": report.rate_limit.median_response_ms
        }
        
    print(json.dumps(out, indent=2))

def version_callback(value: bool):
    if value:
        print("scraperecon v0.1.0")
        raise typer.Exit()

@app.command()
def main(
    url: str = typer.Argument(..., help="Target URL"),
    probe_rate: bool = typer.Option(False, "--probe-rate", help="Run stage 4 (rate limit probe)"),
    concurrency: int = typer.Option(5, "--concurrency", help="Workers for rate probe"),
    requests: int = typer.Option(20, "--requests", help="Total requests for rate probe"),
    impersonate: str = typer.Option(
        "chrome131",
        "--impersonate",
        callback=validate_impersonation_profile,
        help="TLS profile for stage 2: chrome131, chrome120, safari170",
    ),
    timeout: int = typer.Option(10, "--timeout", help="Per-request timeout in seconds"),
    json_out: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
    skip_tls: bool = typer.Option(False, "--skip-tls", help="Skip stage 2"),
    skip_vendor: bool = typer.Option(False, "--skip-vendor", help="Skip stage 3"),
    save: bool = typer.Option(False, "--save", help="Save the full HTML responses to local files"),
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Print version")
):
    report = run_pipeline(
        url=url,
        probe_rate=probe_rate,
        concurrency=concurrency,
        requests=requests,
        impersonate=impersonate,
        timeout=timeout,
        skip_tls=skip_tls,
        skip_vendor=skip_vendor
    )
    
    if json_out:
        print_json(report)
    else:
        print_human(report)
        
    if save:
        from urllib.parse import urlparse
        domain = urlparse(report.target).netloc or "target"
        domain = domain.replace(":", "_")
        
        console = Console()
        console.print()
        console.print("[bold]Saved Files[/bold]")
        
        if report.plain and not report.plain.error and report.plain.full_body:
            fname = f"{domain}_stage1.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report.plain.full_body)
            console.print(f"  [green]Stage 1 saved to:[/green] {fname}")
            
        if report.tls and report.tls.verdict not in (Verdict.SKIPPED, Verdict.ERROR) and report.tls.full_body:
            fname = f"{domain}_stage2.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report.tls.full_body)
            console.print(f"  [green]Stage 2 saved to:[/green] {fname}")
        
if __name__ == "__main__":
    app()
