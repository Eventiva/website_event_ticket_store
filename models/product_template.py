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
        """Set event when ticket is selected"""
        if self.event_ticket_id:
            self.event_id = self.event_ticket_id.event_id

    @api.onchange('service_tracking')
    def _onchange_service_tracking(self):
        """Clear event fields when service_tracking changes"""
        if self.service_tracking != 'event':
            self.event_id = False
            self.event_ticket_id = False

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
