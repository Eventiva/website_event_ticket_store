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

        # Check if ticket is available for sale
        if not self.event_ticket_id.sale_available:
            return False

        # Check if event is not expired
        if self.event_ticket_id.event_id.date_end and self.event_ticket_id.event_id.date_end < fields.Date.today():
            return False

        # Check seat availability if limited
        if self.event_ticket_id.seats_limited and self.event_ticket_id.seats_available <= 0:
            return False

        return True

