"""
Pure requests-based SOAP client for Tiaknight.

Handles the 'Are you human?' interstitial without Playwright/browser binaries.
Uses requests.Session to maintain cookies across the interstitial flow.

Usage (standalone):
    python3 scripts/soap_client.py
"""
import os
import re
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

SOAP_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:ser="http://www.tiaknightfabrics.co.uk/api/soap/service">
<soapenv:Header>
 <ser:VSAuth>
  <ClientID>{clientid}</ClientID>
  <Username>{username}</Username>
  <Password>{password}</Password>
 </ser:VSAuth>
</soapenv:Header>
<soapenv:Body>
 <ser:GetNewOrders>
  <auto_update>{auto_update}</auto_update>
  <file_type>{file_type}</file_type>
 </ser:GetNewOrders>
</soapenv:Body>
</soapenv:Envelope>"""

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _bypass_interstitial(session, url, html_text):
    """Parse the 'Are you human?' interstitial page and extract the
    ayh_access token so we can proceed without a real browser.

    Common patterns observed:
      - <a href="...?ayh_access=TOKEN">Enter Website.</a>
      - <a onclick="location.href='...?ayh_access=TOKEN'">Enter Website.</a>
      - JS: window.location = '...?ayh_access=TOKEN'
    """
    # Pattern 0: JS variable  var accessCode = "TOKEN"  (the enterSite() function)
    js_match = re.search(r'(?:var\s+)?accessCode\s*=\s*["\']([A-Za-z0-9_\-]+)["\']', html_text)
    if js_match:
        return js_match.group(1)

    # Pattern 1: href / URL with ayh_access in it
    match = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', html_text)
    if match:
        return match.group(1)

    # Pattern 2: look for a redirect URL in meta refresh
    meta = re.search(r'<meta\s+http-equiv=["\']refresh["\'].*?url=([^"\'>\s]+)', html_text, re.I)
    if meta:
        redirect_url = meta.group(1)
        m2 = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', redirect_url)
        if m2:
            return m2.group(1)
        # Follow the redirect
        resp = session.get(redirect_url, timeout=15)
        m3 = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', resp.text)
        if m3:
            return m3.group(1)

    # Pattern 3: follow any link on the page that leads to the same domain
    links = re.findall(r'href=["\']([^"\']+)["\']', html_text)
    parsed_base = urllib.parse.urlparse(url)
    for link in links:
        if 'ayh_access' in link:
            m = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', link)
            if m:
                return m.group(1)
        # Follow links on the same domain
        parsed_link = urllib.parse.urlparse(link)
        if parsed_link.netloc and parsed_link.netloc != parsed_base.netloc:
            continue
        if link.startswith('/') or parsed_link.netloc == parsed_base.netloc:
            abs_link = urllib.parse.urljoin(url, link)
            try:
                resp = session.get(abs_link, timeout=15)
                m = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', resp.url)
                if m:
                    return m.group(1)
                m = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', resp.text)
                if m:
                    return m.group(1)
            except Exception:
                continue

    return None


def fetch_soap_response(url, clientid, username, password,
                        auto_update='false', file_type='xml',
                        verify_ssl=True):
    """Fetch the raw SOAP response bytes from Tiaknight.

    Returns (bytes, status_code) — the raw XML bytes of the HTTP response body.
    Raises RuntimeError on unrecoverable failure.
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': DEFAULT_UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })

    envelope = SOAP_TEMPLATE.format(
        clientid=clientid,
        username=username,
        password=password,
        auto_update=auto_update,
        file_type=file_type,
    )

    soap_headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '',
    }

    # ── Attempt 1: Direct POST ────────────────────────────────────────
    try:
        resp = session.post(url, data=envelope.encode('utf-8'),
                            headers=soap_headers, verify=verify_ssl, timeout=30)
    except requests.RequestException as e:
        raise RuntimeError(f"SOAP POST failed: {e}")

    # Check if we got the interstitial instead of real XML
    content_type = resp.headers.get('Content-Type', '')
    body_text = resp.text[:2000]

    is_interstitial = (
        'are you human' in body_text.lower()
        or ('text/html' in content_type.lower() and '<!DOCTYPE' in body_text[:500])
    )

    if not is_interstitial:
        # Got a real SOAP response on first try
        return resp.content, resp.status_code

    # ── Interstitial detected — handle it ─────────────────────────────
    # Step A: GET the page to see the interstitial properly
    try:
        get_resp = session.get(url, verify=verify_ssl, timeout=15)
    except requests.RequestException as e:
        raise RuntimeError(f"GET for interstitial failed: {e}")

    ayh_token = _bypass_interstitial(session, url, get_resp.text)

    # Build target URL with ayh_access if we found it
    target_url = url
    if ayh_token:
        sep = '&' if '?' in url else '?'
        target_url = f"{url}{sep}ayh_access={ayh_token}"

    # Also check if the GET redirected us and the final URL has the token
    if not ayh_token:
        m = re.search(r'ayh_access=([A-Za-z0-9_\-]+)', get_resp.url)
        if m:
            ayh_token = m.group(1)
            sep = '&' if '?' in url else '?'
            target_url = f"{url}{sep}ayh_access={ayh_token}"

    # ── Attempt 2: POST with cookies + ayh_access ─────────────────────
    try:
        resp2 = session.post(target_url, data=envelope.encode('utf-8'),
                             headers=soap_headers, verify=verify_ssl, timeout=30)
    except requests.RequestException as e:
        raise RuntimeError(f"SOAP POST (retry with ayh) failed: {e}")

    # Check again
    body2 = resp2.text[:2000]
    if 'are you human' in body2.lower():
        raise RuntimeError(
            "Could not bypass interstitial with requests. "
            "The anti-bot check may require JavaScript execution. "
            "Install Playwright on the server: pip install playwright && playwright install chromium"
        )

    return resp2.content, resp2.status_code


def extract_result_xml(soap_bytes):
    """Parse raw SOAP bytes and return the text content of <Result><value>,
    which contains the embedded orders XML string. Returns None if not found."""
    try:
        root = ET.fromstring(soap_bytes)
    except ET.ParseError:
        return None

    for item in root.iter('item'):
        key_el = item.find('key')
        val_el = item.find('value')
        if key_el is not None and (key_el.text or '').strip() == 'Result':
            return (val_el.text or '').strip() if val_el is not None else None
    return None


# ── Standalone usage ──────────────────────────────────────────────────────
if __name__ == '__main__':
    url = os.environ.get('TIA_URL', 'https://www.tiaknightfabrics.co.uk/api/soap/service')
    cid = os.environ.get('TIA_CLIENTID', 'Tiaknightfabrics')
    usr = os.environ.get('TIA_USERNAME', 'UserTiaknightfabrics341')
    pwd = os.environ.get('TIA_PASSWORD', 'QdtsC3rm')

    print(f"Fetching from {url} ...")
    raw, code = fetch_soap_response(url, cid, usr, pwd)
    print(f"HTTP {code} — {len(raw)} bytes")

    orders_xml = extract_result_xml(raw)
    if orders_xml:
        print(f"Extracted orders XML ({len(orders_xml)} chars)")
        print(orders_xml[:500])
    else:
        print("No <Result> found in response")
        print(raw[:1000].decode('utf-8', errors='replace'))
