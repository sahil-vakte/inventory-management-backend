#!/usr/bin/env python3
"""Print the exact Tiaknight SOAP request configuration used by WIMS.

This script is read-only. It does not call Tiaknight and does not change DB data.

Usage:
    python scripts/print_tiaknight_request_info.py
    python scripts/print_tiaknight_request_info.py --show-password
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.soap_client import DEFAULT_TIA_URL, DEFAULT_UA, build_get_new_orders_envelope, normalize_service_url


def mask_secret(value):
    if not value:
        return ''
    if len(value) <= 4:
        return '****'
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def main():
    parser = argparse.ArgumentParser(description='Print Tiaknight SOAP request info.')
    parser.add_argument('--env-file', default='.env', help='Path to .env file. Default: .env')
    parser.add_argument(
        '--show-password',
        action='store_true',
        help='Print the real TIA_PASSWORD. Do not use this when sharing output.',
    )
    args = parser.parse_args()

    load_dotenv(dotenv_path=args.env_file)

    url = normalize_service_url(os.environ.get('TIA_URL', DEFAULT_TIA_URL))
    clientid = os.environ.get('TIA_CLIENTID', '')
    username = os.environ.get('TIA_USERNAME', '')
    password = os.environ.get('TIA_PASSWORD', '')
    auto_update = os.environ.get('TIA_AUTO_UPDATE', 'false')
    file_type = os.environ.get('TIA_FILE_TYPE', 'xml')

    display_password = password if args.show_password else mask_secret(password)

    payload = build_get_new_orders_envelope(
        url=url,
        clientid=clientid,
        username=username,
        password=display_password,
        auto_update=auto_update,
        file_type=file_type,
    )

    missing = [
        key for key, value in {
            'TIA_URL': url,
            'TIA_CLIENTID': clientid,
            'TIA_USERNAME': username,
            'TIA_PASSWORD': password,
        }.items()
        if not value
    ]

    print('Tiaknight SOAP request used by WIMS')
    print('==================================')
    print()
    print(f"env_file: {args.env_file}")
    print(f"env_status: {'missing ' + ', '.join(missing) if missing else 'ok'}")
    print()
    print('Request')
    print('-------')
    print(f"POST {url or '<missing TIA_URL>'}")
    print()
    print('Headers')
    print('-------')
    print('Content-Type: text/xml; charset=utf-8')
    print('SOAPAction:')
    print(f'User-Agent: {DEFAULT_UA}')
    print('Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
    print()
    print('Payload')
    print('-------')
    print(payload)
    print()
    print('Notes')
    print('-----')
    print('SOAP version: SOAP 1.1')
    print('Operation: GetNewOrders')
    print('This script does not call Tiaknight.')
    if not args.show_password:
        print('Password is masked. Use --show-password only for private server debugging.')


if __name__ == '__main__':
    main()
