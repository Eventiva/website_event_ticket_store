# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Event and ticket fields for event products
    event_id = fields.Many2one(
        'event.event',
        string='Event',
        help="Select the event for this product. Only used when service_tracking is 'event'."
    )
    event_ticket_id = fields.Many2one(
        'event.event.ticket',
        string='Event Ticket',
        domain="[('event_id', '=', event_id)]",
        help="Select the specific ticket type for this product. Only used when service_tracking is 'event'."
    )

    @api.onchange('event_id')
    def _onchange_event_id(self):
        """Clear ticket selection when event changes"""
        if self.event_id:
            # Reset ticket if it doesn't belong to the selected event
            if self.event_ticket_id and self.event_ticket_id.event_id != self.event_id:
                self.event_ticket_id = False
        else:
            self.event_ticket_id = False

    @api.onchange('event_ticket_id')
    def _onchange_event_ticket_id(self):
        """Set event and price when ticket is selected"""
        if self.event_ticket_id:
            self.event_id = self.event_ticket_id.event_id
            # Update the list price to match the event ticket price
            self.list_price = self.event_ticket_id.price

    @api.onchange('service_tracking')
    def _onchange_service_tracking(self):
        """Clear event fields when service_tracking changes"""
        if self.service_tracking != 'event':
            self.event_id = False
            self.event_ticket_id = False

    def _sync_event_ticket_price(self):
        """Sync product price with event ticket price"""
        for product in self:
            if product.service_tracking == 'event' and product.event_ticket_id:
                product.list_price = product.event_ticket_id.price

    def _update_price_from_event_ticket(self, event_ticket):
        """Update price when event ticket price changes"""
        products = self.search([
            ('service_tracking', '=', 'event'),
            ('event_ticket_id', '=', event_ticket.id)
        ])
        for product in products:
            product.list_price = event_ticket.price

    @api.model
    def create(self, vals):
        """Override create to sync price with event ticket"""
        product = super().create(vals)
        product._sync_event_ticket_price()
        return product

    def write(self, vals):
        """Override write to sync price with event ticket"""
        result = super().write(vals)
        self._sync_event_ticket_price()
        return result

    def _get_event_info(self):
        """Get event information for display purposes"""
        self.ensure_one()
        if not self.event_id or not self.event_ticket_id:
            return {}

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

    def _is_event_ticket_available(self):
        """Check if the event ticket is available for purchase"""
        self.ensure_one()
        if not self.event_ticket_id:
            return False

        # Check if ticket is available for sale
        if not self.event_ticket_id.sale_available:
            return False

        # Check if event is not expired
        if self.event_ticket_id.event_id.date_end and self.event_ticket_id.event_id.date_end.date() < fields.Date.today():
            return False

        # Check seat availability if limited
        if self.event_ticket_id.seats_limited and self.event_ticket_id.seats_available <= 0:
            return False

        return True

