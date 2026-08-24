#!/usr/bin/env python3
"""Dump the raw Tiaknight SOAP response for investigation/sharing.

This script is read-only by default. It calls GetNewOrders with
auto_update=false unless explicitly overridden.

Usage:
    python scripts/dump_tiaknight_response.py
    python scripts/dump_tiaknight_response.py --out-dir logs/tiaknight_debug
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.soap_client import DEFAULT_TIA_URL, fetch_soap_response, fetch_order_response, extract_result_xml


def extract_order_refs(orders_xml):
    if not orders_xml:
        return []
    try:
        root = ET.fromstring(orders_xml)
    except ET.ParseError:
        return []

    orders = [root] if _local_name(root.tag).lower() in {'order', 'web_order'} else list(root)
    refs = []
    for order_elem in orders:
        direct_order_node = _first_direct_child(order_elem, 'order')
        order_node = direct_order_node if direct_order_node is not None else order_elem
        ref = (
            _find_text(order_node, 'order_reference')
            or _find_text(order_node, 'order_id')
            or _find_text(order_elem, 'OrderNumber')
        )
        if ref:
            refs.append(ref)
    return refs


def _find_text(element, tag):
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    target = tag.lower()
    for child in list(element):
        if _local_name(child.tag).lower() == target and child.text:
            return child.text.strip()
    return None


def _first_direct_child(element, local_name):
    target = local_name.lower()
    for child in list(element):
        if _local_name(child.tag).lower() == target:
            return child
    return None


def _local_name(tag):
    return str(tag).rsplit('}', 1)[-1]


def main():
    parser = argparse.ArgumentParser(description='Dump raw Tiaknight SOAP response.')
    parser.add_argument('--env-file', default='.env', help='Path to .env file.')
    parser.add_argument('--out-dir', default='logs/tiaknight_debug', help='Directory for output XML files.')
    parser.add_argument('--auto-update', default=None, help='Override TIA_AUTO_UPDATE. Defaults to false.')
    parser.add_argument('--file-type', default=None, help='Override TIA_FILE_TYPE. Defaults to xml.')
    parser.add_argument('--order-ref', default=None, help='Optional order reference for GetOrder, e.g. WEB238336.')
    parser.add_argument('--order-id', default=None, help='Optional numeric order id for GetOrder. Derived from order-ref if omitted.')
    args = parser.parse_args()

    load_dotenv(dotenv_path=args.env_file)

    url = os.environ.get('TIA_URL') or DEFAULT_TIA_URL
    clientid = os.environ.get('TIA_CLIENTID')
    username = os.environ.get('TIA_USERNAME')
    password = os.environ.get('TIA_PASSWORD')
    auto_update = args.auto_update if args.auto_update is not None else 'false'
    file_type = args.file_type or os.environ.get('TIA_FILE_TYPE', 'xml')

    missing = [
        key for key, value in {
            'TIA_URL': url,
            'TIA_CLIENTID': clientid,
            'TIA_USERNAME': username,
            'TIA_PASSWORD': password,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing required env values: {', '.join(missing)}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

    if args.order_ref:
        soap_bytes, http_status = fetch_order_response(
            url=url,
            clientid=clientid,
            username=username,
            password=password,
            order_ref=args.order_ref,
            order_id=args.order_id or _numeric_order_id(args.order_ref),
        )
    else:
        soap_bytes, http_status = fetch_soap_response(
            url=url,
            clientid=clientid,
            username=username,
            password=password,
            auto_update=auto_update,
            file_type=file_type,
        )
    orders_xml = extract_result_xml(soap_bytes)
    order_refs = extract_order_refs(orders_xml)

    operation = f'get_order_{args.order_ref}' if args.order_ref else 'get_new_orders'
    safe_operation = ''.join(ch for ch in operation if ch.isalnum() or ch in '-_')
    raw_path = out_dir / f'tiaknight_raw_soap_{safe_operation}_{timestamp}.xml'
    raw_path.write_bytes(soap_bytes)

    orders_path = None
    if orders_xml is not None:
        orders_path = out_dir / f'tiaknight_orders_result_{safe_operation}_{timestamp}.xml'
        orders_path.write_text(orders_xml, encoding='utf-8')

    print(f"HTTP status: {http_status}")
    print(f"operation: {'GetOrder' if args.order_ref else 'GetNewOrders'}")
    if args.order_ref:
        print(f"order_ref: {args.order_ref}")
        print(f"order_id: {args.order_id or _numeric_order_id(args.order_ref) or '-'}")
    print(f"auto_update: {auto_update}")
    print(f"file_type: {file_type}")
    print(f"orders_received: {len(order_refs)}")
    print(f"order_refs: {', '.join(order_refs) or '-'}")
    print(f"raw_soap_file: {raw_path}")
    print(f"orders_xml_file: {orders_path or '-'}")


def _numeric_order_id(order_ref):
    value = str(order_ref or '').strip()
    digits = []
    for char in reversed(value):
        if char.isdigit():
            digits.append(char)
        else:
            break
    return ''.join(reversed(digits))


if __name__ == '__main__':
    main()
