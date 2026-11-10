#!/usr/bin/env python3
"""Honest external link verification tool (Python standard library only).

Classifies external links into verified (PASS), definitively broken (FAIL),
or transiently unavailable (INCONCLUSIVE). Never treats HTTP 429, 500, 502,
503, or 504 as verified success.
"""

from __future__ import annotations

import argparse
import glob
import http.client
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set, Tuple

# URL extraction pattern for Markdown links and images
MARKDOWN_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\((https?://[^)\s]+)(?:\s+\"[^\"]*\")?\)")

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; PortfolioLinkChecker/1.0; +https://github.com/gthgomez)"
DEFAULT_EXCLUDED_PATTERNS = [
    re.compile(r"^https?://(www\.)?linkedin\.com", re.IGNORECASE),
]

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INCONCLUSIVE = "INCONCLUSIVE"

# HTTP status codes that represent transient availability or server-side issues
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class LinkCheckResult:
    def __init__(
        self,
        url: str,
        status: str,
        http_code: Optional[int] = None,
        message: str = "",
        attempts: int = 1,
    ):
        self.url = url
        self.status = status  # PASS, FAIL, INCONCLUSIVE
        self.http_code = http_code
        self.message = message
        self.attempts = attempts

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status": self.status,
            "http_code": self.http_code,
            "message": self.message,
            "attempts": self.attempts,
        }


def extract_external_links_from_file(
    file_path: str,
    excluded_patterns: Optional[List[re.Pattern]] = None,
) -> Set[str]:
    """Extract all external HTTP(S) URLs from a Markdown file."""
    if excluded_patterns is None:
        excluded_patterns = DEFAULT_EXCLUDED_PATTERNS

    links: Set[str] = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return links

    for match in MARKDOWN_LINK_RE.finditer(content):
        url = match.group(3).strip()
        # Clean trailing punctuation from URL if accidentally captured
        url = url.rstrip(".,;:")
        # Check exclusion patterns
        if any(p.search(url) for p in excluded_patterns):
            continue
        links.add(url)

    return links


def classify_http_response(status_code: int, reason: str = "") -> Tuple[str, str]:
    """Classify an HTTP status code into PASS, FAIL, or INCONCLUSIVE."""
    if 200 <= status_code < 400:
        return STATUS_PASS, f"HTTP {status_code} {reason}".strip()
    if status_code in TRANSIENT_STATUS_CODES:
        return STATUS_INCONCLUSIVE, f"Transient HTTP {status_code} {reason}".strip()
    return STATUS_FAIL, f"Definitive HTTP {status_code} {reason}".strip()


def check_url(
    url: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    opener: Optional[urllib.request.OpenerDirector] = None,
) -> LinkCheckResult:
    """Check a single external URL with bounded retries and exponential backoff.
    
    Injected HTTP 404, 429, 500, and 504 responses are classified deterministically:
    - 200..=399 -> PASS
    - 404, 400..=428, 430..=499 -> FAIL
    - 429, 500, 502, 503, 504, timeout -> INCONCLUSIVE
    """
    if opener is None:
        opener = urllib.request.build_opener()

    last_status = STATUS_FAIL
    last_code: Optional[int] = None
    last_message = ""

    for attempt in range(1, max_retries + 1):
        # Try HEAD request first, fallback to GET with bounded range
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "*/*",
            },
            method="HEAD",
        )

        try:
            with opener.open(req, timeout=timeout) as resp:
                code = getattr(resp, "status", resp.getcode())
                classification, msg = classify_http_response(code, getattr(resp, "reason", "OK"))
                return LinkCheckResult(url, classification, code, msg, attempt)
        except urllib.error.HTTPError as e:
            code = e.code
            last_code = code
            # 405 Method Not Allowed or 403 on HEAD -> try GET with minimal range
            if code in (405, 403) and attempt == 1:
                get_req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": DEFAULT_USER_AGENT,
                        "Accept": "*/*",
                        "Range": "bytes=0-512",
                    },
                    method="GET",
                )
                try:
                    with opener.open(get_req, timeout=timeout) as get_resp:
                        get_code = getattr(get_resp, "status", get_resp.getcode())
                        classification, msg = classify_http_response(get_code, getattr(get_resp, "reason", "OK"))
                        return LinkCheckResult(url, classification, get_code, msg, attempt)
                except urllib.error.HTTPError as get_e:
                    code = get_e.code
                    last_code = code
                except Exception:
                    pass

            classification, msg = classify_http_response(code, e.reason)
            last_status = classification
            last_message = msg

            # If definitive error (like 404 Not Found), do not retry
            if classification == STATUS_FAIL:
                return LinkCheckResult(url, STATUS_FAIL, code, msg, attempt)

            # If transient (429, 500, 502, 503, 504), back off and retry
            if attempt < max_retries:
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue

        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            reason = getattr(e, "reason", str(e))
            if isinstance(reason, socket.gaierror):
                # DNS resolution failure is definitive
                return LinkCheckResult(url, STATUS_FAIL, None, f"DNS failure: {reason}", attempt)
            # Timeouts and connection resets are transient
            last_status = STATUS_INCONCLUSIVE
            last_message = f"Network timeout/error: {reason}"
            if attempt < max_retries:
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                continue

        except Exception as e:
            last_status = STATUS_FAIL
            last_message = f"Unexpected error: {e}"
            return LinkCheckResult(url, STATUS_FAIL, None, last_message, attempt)

    return LinkCheckResult(url, last_status, last_code, last_message, max_retries)


def run_link_check(
    root_dir: str = ".",
    exclude_dirs: Optional[List[str]] = None,
    timeout: float = 10.0,
    max_retries: int = 3,
    fail_on_inconclusive: bool = False,
) -> Tuple[int, List[LinkCheckResult]]:
    """Scan all Markdown files in root_dir, check links, and return exit code + results."""
    if exclude_dirs is None:
        exclude_dirs = ["node_modules", ".git", "fixtures", "tools/tests/fixtures"]

    md_files: List[str] = []
    for root, dirs, files in os.walk(root_dir):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if not any(os.path.join(root, d).replace("\\", "/").endswith(ex) for ex in exclude_dirs)]
        for f in files:
            if f.endswith(".md"):
                rel_path = os.path.relpath(os.path.join(root, f), root_dir).replace("\\", "/")
                if not any(ex in rel_path for ex in exclude_dirs):
                    md_files.append(os.path.join(root, f))

    all_links: Set[str] = set()
    for md_file in md_files:
        all_links.update(extract_external_links_from_file(md_file))

    results: List[LinkCheckResult] = []
    failed_count = 0
    inconclusive_count = 0
    passed_count = 0

    print(f"Scanning {len(md_files)} Markdown files for external links...")
    print(f"Found {len(all_links)} unique external URLs to verify.\n")

    for url in sorted(all_links):
        res = check_url(url, timeout=timeout, max_retries=max_retries)
        results.append(res)
        tag = f"[{res.status}]"
        code_str = f"({res.http_code})" if res.http_code else ""
        print(f"{tag:<16} {res.url} {code_str} {res.message}")
        if res.status == STATUS_FAIL:
            failed_count += 1
        elif res.status == STATUS_INCONCLUSIVE:
            inconclusive_count += 1
        else:
            passed_count += 1

    print("\n--- Summary ---")
    print(f"Total checked: {len(results)}")
    print(f"PASS (Verified): {passed_count}")
    print(f"FAIL (Broken):   {failed_count}")
    print(f"INCONCLUSIVE:    {inconclusive_count}")

    if failed_count > 0:
        return 1, results
    if fail_on_inconclusive and inconclusive_count > 0:
        return 1, results
    return 0, results


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify external Markdown links honestly.")
    parser.add_argument("--repo", default=".", help="Root repository directory.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries for transient codes.")
    parser.add_argument(
        "--fail-on-inconclusive",
        action="store_true",
        help="Fail (exit 1) if any link returns INCONCLUSIVE (transient error). Default warns.",
    )

    args = parser.parse_args()
    exit_code, _ = run_link_check(
        root_dir=args.repo,
        timeout=args.timeout,
        max_retries=args.max_retries,
        fail_on_inconclusive=args.fail_on_inconclusive,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
