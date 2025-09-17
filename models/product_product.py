# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Event ticket field for one-to-one relationship with variants
    event_ticket_id = fields.Many2one(
        'event.event.ticket',
        string='Event Ticket',
        help="Select the specific ticket type for this product variant. Each variant should have its own ticket."
    )

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        """Clear event_ticket_id when product template changes"""
        if not self.product_tmpl_id.event_id:
            self.event_ticket_id = False

    @api.onchange('event_ticket_id')
    def _onchange_event_ticket_id(self):
        """Validate that the selected ticket belongs to the product template's event"""
        if self.event_ticket_id and self.product_tmpl_id.event_id:
            if self.event_ticket_id.event_id != self.product_tmpl_id.event_id:
                self.event_ticket_id = False
                return {
                    'warning': {
                        'title': _('Invalid Ticket'),
                        'message': _('The selected ticket does not belong to the event configured for this product template. Please select a ticket for the correct event.'),
                    }
                }

    def _get_event_info(self):
        """Get event information for display purposes"""
        self.ensure_one()
        if not self.event_ticket_id:
            return self.product_tmpl_id._get_event_info()

        return {
            'event_name': self.event_ticket_id.event_id.name,
            'event_date_begin': self.event_ticket_id.event_id.date_begin,
            'event_date_end': self.event_ticket_id.event_id.date_end,
            'ticket_name': self.event_ticket_id.name,
            'ticket_price': self.event_ticket_id.price,
            'ticket_price_reduce': self.event_ticket_id.price_reduce,
            'seats_available': self.event_ticket_id.seats_available if self.event_ticket_id.seats_limited else None,
            'seats_limited': self.event_ticket_id.seats_limited,
            'ticket_description': self.event_ticket_id.description or '',
            'is_available': self._is_event_ticket_available(),
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

