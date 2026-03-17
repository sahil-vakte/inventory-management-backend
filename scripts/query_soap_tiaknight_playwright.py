#!/usr/bin/env python3
"""Use Playwright to execute the site's JS 'Are you human' flow, then POST the SOAP envelope with the session cookies.

Requirements:
  pip install playwright requests
  python -m playwright install

Usage:
  python3 scripts/query_soap_tiaknight_playwright.py --out response_playwright.xml
  python3 scripts/query_soap_tiaknight_playwright.py --insecure --headful
"""
import argparse
import os
import sys
import requests
import urllib.parse
from xml.dom import minidom
import xml.etree.ElementTree as ET
import json
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("Playwright is not installed. Install with: pip install playwright && python -m playwright install")
    raise


SOAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
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

</soapenv:Envelope>
"""


def pretty_xml(xml_bytes):
    try:
        return minidom.parseString(xml_bytes).toprettyxml(indent='  ')
    except Exception:
        try:
            return xml_bytes.decode('utf-8', errors='replace')
        except Exception:
            return str(xml_bytes)


def strip_ns(tag):
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def element_to_dict(elem):
    """Convert an ElementTree element to a dict (simple: child tag -> text)."""
    d = {}
    # include attributes
    for k, v in elem.attrib.items():
        d[k] = v
    # children
    for child in list(elem):
        key = strip_ns(child.tag)
        text = (child.text or '').strip()
        # if child has further children, recurse
        if len(list(child)) > 0:
            d.setdefault(key, [])
            d[key].append(element_to_dict(child))
        else:
            # handle duplicate keys by making list
            if key in d:
                if not isinstance(d[key], list):
                    d[key] = [d[key]]
                d[key].append(text)
            else:
                d[key] = text
    return d


def parse_soap_response(content):
    """Parse SOAP response bytes and return a dict of body contents.

    Heuristic: find SOAP Body, then convert first-level children into dicts.
    If elements named 'Order' are found, return them as a list under 'orders'.
    """
    root = ET.fromstring(content)
    # find Body
    body = None
    for child in root.iter():
        if strip_ns(child.tag).lower() == 'body':
            body = child
            break
    if body is None:
        # maybe the response is the payload directly
        body = root

    result = {}
    orders = []
    for child in list(body):
        tag = strip_ns(child.tag)
        # dive one level deeper if wrapper element (like GetNewOrdersResponse)
        if len(list(child)) == 1 and strip_ns(list(child)[0].tag).lower() in ('orders', 'order', 'neworders'):
            inner = list(child)[0]
            for item in list(inner):
                if strip_ns(item.tag).lower() == 'order':
                    orders.append(element_to_dict(item))
                else:
                    # collect other items
                    result.setdefault(strip_ns(inner.tag), []).append(element_to_dict(item))
        else:
            # if this child is an Order element
            if tag.lower() == 'order':
                orders.append(element_to_dict(child))
            else:
                result[tag] = element_to_dict(child)

    if orders:
        result['orders'] = orders

    return result


def run(args):
    envelope = SOAP_TEMPLATE.format(
        clientid=args.clientid,
        username=args.username,
        password=args.password,
        auto_update=args.auto_update,
        file_type=args.file_type,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        context = browser.new_context()
        page = context.new_page()
        print(f"Opening {args.url} in browser (headful={args.headful})...")
        page.goto(args.url, timeout=30000)

        # If page contains the human check, try to click the Enter button
        content = page.content()
        if 'Are you human' in content or 'are you human' in content.lower():
            print("Detected interstitial. Attempting to click the Enter Website button...")
            try:
                # Try several selectors
                if page.locator('text=Enter Website.').count() > 0:
                    page.click('text=Enter Website.')
                elif page.locator('a[onclick]').count() > 0:
                    page.click('a[onclick]')
                else:
                    # fallback: run the JS function if present
                    page.evaluate("() => { if (typeof enterSite === 'function') enterSite(); }")

                page.wait_for_load_state('networkidle', timeout=10000)
                print("Clicked and waited for navigation")
            except Exception as e:
                print(f"Could not interact with interstitial: {e}")

        # After navigation, collect cookies and current URL
        final_url = page.url
        cookies = context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        print(f"Final URL: {final_url}")
        print(f"Cookies: {list(cookie_dict.keys())}")

        # Build headers and use requests to POST the SOAP envelope with cookies
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'User-Agent': args.user_agent,
            'Accept': 'text/xml,application/xml,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
            'Referer': args.url,
        }

        # If final_url contains ayh_access param, include it on target URL as well
        parsed = urllib.parse.urlparse(final_url)
        q = urllib.parse.parse_qs(parsed.query)
        target_url = args.url
        if 'ayh_access' in q:
            sep = '&' if '?' in args.url else '?'
            target_url = f"{args.url}{sep}ayh_access={q['ayh_access'][0]}"
            print(f"Using target URL with ayh_access: {target_url}")

        print(f"POSTing SOAP envelope to {target_url} with cookies")
        try:
            resp = requests.post(target_url, data=envelope.encode('utf-8'), headers=headers, cookies=cookie_dict, verify=not args.insecure, timeout=30)
        except Exception as e:
            print(f"POST failed: {e}")
            browser.close()
            return

        print(f"HTTP {resp.status_code} {resp.reason}")
        if args.out:
            with open(args.out, 'wb') as f:
                f.write(resp.content)
            print(f"Wrote response to {args.out}")

        print("--- Pretty/Truncated Response ---")
        pretty = pretty_xml(resp.content)
        print(pretty[:2000])

        # If parsing requested, attempt to parse SOAP XML and extract orders
        if args.parse:
            try:
                parsed = parse_soap_response(resp.content)
                pretty_json = json.dumps(parsed, indent=2)
                print("--- Parsed SOAP content (JSON) ---")
                print(pretty_json[:2000])
                if args.parsed_out:
                    with open(args.parsed_out, 'w', encoding='utf-8') as pf:
                        pf.write(pretty_json)
                    print(f"Wrote parsed JSON to {args.parsed_out}")
            except Exception as e:
                print(f"Error parsing SOAP response: {e}")
        browser.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default=os.environ.get('TIA_URL', 'https://www.tiaknightfabrics.co.uk/api/soap/service'))
    p.add_argument('--clientid', default=os.environ.get('TIA_CLIENTID', 'Tiaknightfabrics'))
    p.add_argument('--username', default=os.environ.get('TIA_USERNAME', 'UserTiaknightfabrics341'))
    p.add_argument('--password', default=os.environ.get('TIA_PASSWORD', 'QdtsC3rm'))
    p.add_argument('--auto_update', default='false')
    p.add_argument('--file_type', default='xml')
    p.add_argument('--out', help='Write raw response to file', default='response_playwright.xml')
    p.add_argument('--parse', action='store_true', help='Attempt to parse SOAP XML and extract orders')
    p.add_argument('--parsed-out', help='Write parsed JSON output to file')
    p.add_argument('--insecure', action='store_true')
    p.add_argument('--headful', action='store_true', help='Run browser with UI (not headless)')
    p.add_argument('--user-agent', default='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    args = p.parse_args()
    run(args)


if __name__ == '__main__':
    main()
