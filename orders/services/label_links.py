from django.core import signing


PUBLIC_LABEL_SALT = 'orders.public_shipping_label'


def make_public_label_token(order):
    """Build a signed token for opening a saved label without API auth."""
    return signing.dumps(
        {
            'order_id': order.id,
            'shipping_label_file': order.shipping_label_file or '',
        },
        salt=PUBLIC_LABEL_SALT,
    )


def load_public_label_token(token):
    return signing.loads(token, salt=PUBLIC_LABEL_SALT)
