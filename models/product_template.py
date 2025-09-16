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
                # Use context flag to prevent recursion
                product.with_context(skip_price_sync=True).write({
                    'list_price': product.event_ticket_id.price
                })

    def _update_price_from_event_ticket(self, event_ticket):
        """Update price when event ticket price changes"""
        products = self.search([
            ('service_tracking', '=', 'event'),
            ('event_ticket_id', '=', event_ticket.id)
        ])
        for product in products:
            # Use context flag to prevent recursion
            product.with_context(skip_price_sync=True).write({
                'list_price': event_ticket.price
            })

    @api.model
    def create(self, vals):
        """Override create to sync price with event ticket"""
        product = super().create(vals)
        # Only sync if not already setting list_price in vals
        if 'list_price' not in vals:
            product._sync_event_ticket_price()
        return product

    def write(self, vals):
        """Override write to sync price with event ticket"""
        result = super().write(vals)
        # Skip price sync if we're already syncing or if list_price is being updated
        if not self.env.context.get('skip_price_sync') and 'list_price' not in vals:
            # Only sync if it's an event product
            event_products = self.filtered(lambda p: p.service_tracking == 'event')
            if event_products:
                event_products._sync_event_ticket_price()
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

