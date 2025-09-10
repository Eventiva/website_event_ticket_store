# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteEventTicketStore(WebsiteSale):
    """Controller for handling event ticket purchases from the website store"""

    def _get_event_info_for_product(self, product):
        """Get event information for a product to display on the website"""
        if not product or product.service_tracking != 'event':
            return None

        if not product.event_id or not product.event_ticket_id:
            return None

        return {
            'event_name': product.event_id.name,
            'event_date_begin': product.event_id.date_begin,
            'event_date_end': product.event_id.date_end,
            'ticket_name': product.event_ticket_id.name,
            'ticket_price': product.event_ticket_id.price,
            'ticket_price_reduce': product.event_ticket_id.price_reduce,
            'seats_available': product.event_ticket_id.seats_available if product.event_ticket_id.seats_limited else None,
            'seats_limited': product.event_ticket_id.seats_limited,
            'ticket_description': product.event_ticket_id.description or '',
            'is_available': product._is_event_ticket_available(),
        }
