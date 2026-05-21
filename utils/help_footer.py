# -*- coding: utf-8 -*-
"""HTML footer snippets for processing algorithm help (no embedded base64)."""


def social_links_footer() -> str:
    """Author social links for ``shortHelpString`` footers."""
    return (
        '<p align="right">'
        '<a target="_blank" rel="noopener noreferrer" href="https://github.com/thangqd">'
        "GitHub</a> · "
        '<a target="_blank" rel="noopener noreferrer" href="https://www.linkedin.com/in/thangqd/">'
        "LinkedIn</a>"
        "</p>"
    )
