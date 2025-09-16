# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Event field for event products (tickets are now handled at variant level)
    event_id = fields.Many2one(
        'event.event',
        string='Event',
        help="Select the event for this product template. Individual variants will have their own tickets."
    )

    @api.onchange('service_tracking')
    def _onchange_service_tracking(self):
        """Clear event fields when service_tracking changes"""
        if self.service_tracking != 'event':
            self.event_id = False

    def _get_event_info(self):
        """Get event information for display purposes"""
        self.ensure_one()
        if not self.event_id or not self.event_ticket_id:
            return {}

        return {
            'event_name': self.event_id.name,
            'event_date_begin': self.event_id.date_begin,
            'event_date_end': self.event_id.date_end,
        }
