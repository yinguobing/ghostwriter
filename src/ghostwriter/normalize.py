"""Unicode title normalization for WeChat compatibility.

WeChat's draft API (error 45003) rejects titles containing certain
Unicode characters. This module maps them to safe ASCII equivalents.
"""


def normalize_title(title):
    """Replace Unicode special characters with ASCII equivalents.

    Mappings:
        “ ”  (curly double quotes)  → "
        ‘ ’  (curly single quotes)  → '
        — –  (em/en dash)            → -
        　         (fullwidth space)       → " "
    """
    return (
        title
        .replace('“', '"').replace('”', '"')
        .replace('‘', "'").replace('’', "'")
        .replace('—', '-').replace('–', '-')
        .replace('　', ' ')
    )
