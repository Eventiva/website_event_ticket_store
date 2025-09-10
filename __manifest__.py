# -*- coding: utf-8 -*-
{
    'name': 'Website Event Ticket Store',
    'version': '18.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Allow event tickets to be purchased from the website store',
    'description': """
Website Event Ticket Store
==========================

This module allows event tickets to be purchased directly from the website store
by automatically setting the required event and ticket fields when adding event
products to the cart.

Features:
---------
* Automatically sets event_id and event_ticket_id when adding event products to cart
* Provides a selection interface for event tickets on the website
* Handles validation for event ticket purchases
* Works with existing event_sale functionality

Technical Details:
------------------
* Extends sale.order.line to add proper event fields (not x_studio_ fields)
* Overrides website_sale cart logic to handle event ticket selection
* Provides website templates for event ticket selection
* Maintains compatibility with existing event_sale module
    """,
    'author': 'Eventiva',
    'website': 'https://www.eventiva.com',
    'depends': [
        'website_sale',
        'event_sale',
        'website_event_sale',
    ],
    'data': [
        'views/product_template_views.xml',
        'views/sale_order_line_views.xml',
        'views/website_sale_templates.xml',
        'security/ir.model.access.csv',
    ],
    'test': [
        'tests/test_event_ticket_store.py',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'Other OSI approved licence',
}
