# scraperecon

Run this before you write a scraper. It tells you what bot protection a site has, whether plain HTTP or TLS impersonation is enough to get through, and how aggressively it rate limits — before you've written a single line of scraper code.

<img width="1117" height="409" alt="image" src="https://github.com/user-attachments/assets/aa7d0670-c612-4cfb-a579-b610b9c04163" />

<br/>

## Usage

```bash
scraperecon https://target.com
```

```
scraperecon — https://target.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scrape Report
  robots.txt: https://target.com/robots.txt
  robots.txt blocks scraping, proceed at own caution
  Sitemap:    12,843 URLs across 4 sitemap file(s)

Stage 1 — Plain HTTP (httpx, scraper User-Agent)
  Status:   403 Forbidden
  Time:     212ms
  Verdict:  Blocked

Stage 2 — TLS Impersonation (chrome131)
  Status:   200 OK
  Time:     389ms
  Verdict:  Open
  Note:     TLS fingerprint was the blocker ✓

Stage 3 — Vendor Detection
  Vendor:     Cloudflare
  Confidence: High
  Signals:    cf-ray header, __cf_bm cookie, challenges.cloudflare.com in body

Stage 4 — Rate Limit Probe
  Skipped (pass --probe-rate to enable)

Embedded Data Patterns (2/5 detected in Stage 2 (chrome131))
Pattern                 Detected  Signal                              Why It Matters
JSON-LD                 Yes       script[type="application/ld+json"]  Parse schema payloads for product,
                                                                      article, job, or org fields.
Next.js hydration       Yes       script#__NEXT_DATA__                Read props/pageProps from the
                                                                      Next.js bootstrap JSON.
Nuxt payload            No        window.__NUXT__ or data-nuxt-data   Inspect the Nuxt payload for
                                                                      server-rendered entities and route data.
Apollo/Relay cache      No        window.__APOLLO_STATE__ or          Extract normalized GraphQL entities
                                  __RELAY_PAYLOADS__                  from the hydrated client cache.
Bootstrapped app state  No        window.__INITIAL_STATE__ or         Mine the initial Redux-style store
                                  __PRELOADED_STATE__                 for records already sent to the client.

Recommendation
  Use curl_cffi with chrome131 TLS profile
  No CAPTCHA detected at probe volume
  Proxy rotation not required at low request rates
```

---

## What it does

scraperecon starts with a scrape report, then runs four stages against a URL in order, stopping early where it can.

**Scrape Report**

Fetches `robots.txt` before the network challenge stages. If the target path is disallowed for generic crawlers, scraperecon prints:

```text
robots.txt blocks scraping, proceed at own caution
```

It also discovers sitemap URLs from `robots.txt`, falls back to `/sitemap.xml` when needed, follows sitemap indexes recursively, and counts the number of page URLs found. This is useful for sizing a site before you write a scraper.

**Stage 1 — Plain HTTP**

A basic GET with no tricks. If this comes back clean, you don't need anything else — plain `httpx` or `requests` will work fine and you can stop here.

It also checks whether a 200 response is actually real content or a JS challenge page. Cloudflare in particular loves returning 200 with a challenge rather than a 403. scraperecon catches that and marks it `Challenged` instead of lying to you with a green `Open`.

**Stage 2 — TLS Impersonation**

If Stage 1 was blocked or challenged, it retries using `curl_cffi` impersonating Chrome's TLS fingerprint. A lot of bot detection happens at the TLS handshake level — Python's `requests` library has a completely different fingerprint from a real browser, and that alone is enough to get you blocked on many sites before the server has even looked at your headers. If Stage 2 passes where Stage 1 didn't, you know exactly what the fix is.

**Stage 3 — Vendor Detection**

Inspects headers, cookies, and the response body for known signatures and tells you which bot protection vendor is running. This matters because Cloudflare, DataDome, Akamai, and PerimeterX all require different bypass strategies. Knowing which one you're dealing with upfront saves you from trying things that were never going to work.

**Stage 4 — Rate Limit Probe** _(opt-in)_

Fires N requests with configurable concurrency and watches what happens — hard 429s, silent response time degradation, mid-session redirects. Off by default because blasting a site without thinking about it is bad practice. Pass `--probe-rate` when you actually need the data.

**Embedded Data Patterns**

Checks the best HTML body it retrieved and reports five common client-visible data formats that are often directly scrapable without browser automation:

- JSON-LD
- Next.js `__NEXT_DATA__`
- Nuxt `__NUXT__` payloads
- Apollo/Relay hydrated GraphQL caches
- Redux-style bootstrapped app state

If any of these are present, the terminal table tells you what was found and what kind of extraction path is likely to work.
When a payload is valid JSON, it also shows up to 7 top-level keys with a `+ n more` suffix when the object is larger.

---

## Install

```bash
pipx install scraperecon
```

---

## Usage

```bash
scraperecon https://target.com
scraperecon https://target.com --probe-rate
scraperecon https://target.com --probe-rate --concurrency 10 --requests 50
scraperecon https://target.com --impersonate safari170
scraperecon https://target.com --show-sitemap-preview
scraperecon https://target.com --show-embedded-keys
scraperecon https://target.com --save
scraperecon https://target.com --json | jq .recommendation
```

| Flag                     | Default   | Description                                                                          |
| ------------------------ | --------- | ------------------------------------------------------------------------------------ |
| `--probe-rate`           | off       | Run Stage 4 rate limit probe                                                         |
| `--concurrency`          | 5         | Workers for rate probe                                                               |
| `--requests`             | 20        | Total requests for rate probe                                                        |
| `--impersonate`          | chrome131 | TLS profile for Stage 2. Options: `chrome131`, `chrome120`, `safari170` |
| `--timeout`              | 10        | Per-request timeout in seconds                                                       |
| `--json`                 | off       | Machine-readable JSON output                                                         |
| `--show-sitemap-preview` | off       | Show up to 3 sample URLs for each detected sitemap in the human-readable report      |
| `--show-embedded-keys`   | off       | Show parsed top-level keys for embedded data patterns in the human-readable report   |
| `--save`                 | off       | Save the full HTML responses to local files (`<domain>_stage1.html`, etc.)           |
| `--skip-tls`             | off       | Skip Stage 2                                                                         |
| `--skip-vendor`          | off       | Skip Stage 3                                                                         |

---

## Reading the recommendation

At the end of every run you get a plain-English recommendation based on what was found.

- **Plain HTTP should be sufficient** — `httpx` or `requests` will work. No special setup needed.
- **Use curl_cffi with `<profile>`** — TLS fingerprinting is blocking you. Switch to `curl_cffi` with the listed profile.
- **May need browser automation** — both plain and TLS requests were blocked. You're likely looking at a full JS challenge (Turnstile, hCaptcha). Playwright with a stealth plugin is probably your next move.
- **Proxy rotation recommended** — the rate probe hit throttling. At any real request volume you'll need rotating proxies.
- **CAPTCHA detected** — the response body contained CAPTCHA indicators. Automated solving or a managed scraping service required.

---

## JSON output

Pass `--json` to get machine-readable output. Robots and sitemap data live under `scrape_report`, before the stage results.

```json
{
  "target": "https://target.com",
  "scrape_report": {
    "blocked": true,
    "robots_url": "https://target.com/robots.txt",
    "sitemap_url_count": 12843,
    "sitemaps_checked": 4,
    "sitemap_sources": [
      "https://target.com/sitemap.xml",
      "https://target.com/sitemap_0.xml"
    ]
  },
  "stages": {
    "plain": {},
    "tls": {},
    "vendor": {},
    "rate_limit": null
  },
  "scrapable_patterns": [
    {
      "name": "JSON-LD",
      "detected": true,
      "signal": "script[type=\"application/ld+json\"]",
      "extraction_hint": "Parse schema payloads for product, article, job, or org fields."
    }
  ]
}
```

---

## Adding vendor signatures

Signatures live in `scraperecon/data/signatures.json`. It's a flat JSON file — no code required. If you know a signal that's missing, open a PR.

```json
{
  "name": "YourVendor",
  "signals": [
    { "type": "header_present", "key": "x-your-vendor", "weight": 0.8 },
    { "type": "cookie_name", "value": "your_cookie", "weight": 0.6 }
  ]
}
```

Signal types: `header_present`, `header_value`, `cookie_name`, `body_contains`, `status_code`.

---

## What it won't do

scraperecon is a recon tool, not a scraping library. It tells you what you need — it doesn't do it for you. No CAPTCHA solving, no Playwright integration, no proxy support, no persistent history, and no crawling page URLs from sitemap results.

---

Every scraper project starts with the same 20 minutes of manual work: try curl, get blocked, try curl_cffi, check the headers, fire some requests and see what happens. This automates that.
