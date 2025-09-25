# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EventEventTicket(models.Model):
    _inherit = 'event.event.ticket'

    @api.model
    def create(self, vals):
        """Override create to sync price with products"""
        ticket = super().create(vals)
        ticket._sync_price_to_products()
        return ticket

    def write(self, vals):
        """Override write to sync price with products when price changes"""
        result = super().write(vals)
        if 'price' in vals:
            self._sync_price_to_products()
        return result

    def _sync_price_to_products(self):
        """Sync ticket price to all product variants using this ticket"""
        for ticket in self:
            # Find product variants that use this ticket
            variants = self.env['product.product'].search([
                ('service_tracking', '=', 'event'),
                ('event_ticket_id', '=', ticket.id)
            ])
            # Update the list price on the product template for each variant
            for variant in variants:
                # Use context flag to prevent recursion
                variant.product_tmpl_id.with_context(skip_price_sync=True).write({
                    'list_price': ticket.price
                })
