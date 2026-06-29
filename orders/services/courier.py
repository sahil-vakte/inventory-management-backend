import re


COURIER_SERVICE_CODE_MAP = {
    'standard delivery': 'STD',
    'super saver postage': 'STD',
    'international delivery': 'INT',
    'european delivery (5-7 days)': 'INT',
    'next day delivery (next working day if ordered before 1pm)': 'NEXT DAY',
    'next day by 12pm (next working day if ordered before 1pm)': 'NEXT DAY 12',
    'saturday delivery (on orders placed before 1pm)': 'SATURDAY',
    'collect in store': 'Collect in Store',
}


def normalize_courier_service_name(value):
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value).strip())


def courier_service_code(value):
    """Return the label/export code used by WIMS for a Tiaknight courier name."""
    name = normalize_courier_service_name(value)
    if not name:
        return ''

    key = name.lower()
    if key in COURIER_SERVICE_CODE_MAP:
        return COURIER_SERVICE_CODE_MAP[key]

    if 'collect in store' in key:
        return 'Collect in Store'
    if 'saturday delivery' in key:
        return 'SATURDAY'
    if 'next day by 12' in key or 'next day 12' in key:
        return 'NEXT DAY 12'
    if 'next day delivery' in key or key == 'next day':
        return 'NEXT DAY'
    if 'international delivery' in key or 'european delivery' in key:
        return 'INT'
    if 'standard delivery' in key or 'super saver postage' in key:
        return 'STD'

    return ''
