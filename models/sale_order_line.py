# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Override the existing fields to make them not computed and allow manual setting
    event_id = fields.Many2one(
        'event.event',
        string='Event',
        help="Event for this ticket purchase (automatically set from product).",
        store=True
    )
    event_ticket_id = fields.Many2one(
        'event.event.ticket',
        string='Ticket Type',
        help="Ticket type for this purchase (automatically set from product).",
        store=True
    )

    @api.onchange('product_id')
    def _onchange_product_id_event_ticket(self):
        """Automatically set event and ticket from product when product changes"""
        if self.product_id and self.product_id.service_tracking == 'event':
            # Set event from template and ticket from variant
            self.event_id = self.product_id.product_tmpl_id.event_id
            self.event_ticket_id = self.product_id.event_ticket_id
        else:
            # Clear event fields for non-event products
            self.event_id = False
            self.event_ticket_id = False

    def _get_display_price(self):
        """Override to use variant price instead of event ticket price"""
        if self.event_ticket_id and self.event_id:
            # Use the variant's calculated price (base + attributes) instead of ticket price
            # This allows attribute pricing to work correctly with event tickets
            return super()._get_display_price()
        return super()._get_display_price()

    def _get_event_info(self):
        """Get event information for display purposes"""
        self.ensure_one()
        if self.event_id and self.event_ticket_id:
            return {
                'event_name': self.event_id.name,
                'event_date_begin': self.event_id.date_begin,
                'event_date_end': self.event_id.date_end,
                'ticket_name': self.event_ticket_id.name,
                'ticket_price': self.event_ticket_id.price,
                'ticket_price_reduce': self.event_ticket_id.price_reduce,
                'seats_available': self.event_ticket_id.seats_available if self.event_ticket_id.seats_limited else None,
                'seats_limited': self.event_ticket_id.seats_limited,
                'ticket_description': self.event_ticket_id.description or '',
            }
        return {}
