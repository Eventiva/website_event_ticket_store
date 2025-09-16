# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_event_info(self):
        """Get event information for display purposes"""
        self.ensure_one()
        return self.product_tmpl_id._get_event_info()

    def _is_event_ticket_available(self):
        """Check if the event ticket is available for purchase"""
        self.ensure_one()
        if not self.event_ticket_id:
            return False

        ticket = self.event_ticket_id
        now = fields.Datetime.now()

        # Check if ticket is launched (sale has started)
        if ticket.start_sale_datetime and ticket.start_sale_datetime > now:
            return False

        # Check if ticket is expired (sale has ended)
        if ticket.end_sale_datetime and ticket.end_sale_datetime < now:
            return False

        # Check if event is not expired
        if ticket.event_id.date_end and ticket.event_id.date_end < now:
            return False

        # Check seat availability if limited (0 means unlimited)
        if ticket.seats_limited and ticket.seats_available <= 0:
            return False

        return True

