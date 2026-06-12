import re


def normalize_sku_reference(value):
    """Normalize source SKUs like '(109 LT) DSND' to '109 LT DSND'."""
    value = str(value or '').strip()
    value = re.sub(r'\(([^()]*)\)', r'\1', value)
    value = value.replace('(', ' ').replace(')', ' ')
    return re.sub(r'\s+', ' ', value).strip()
