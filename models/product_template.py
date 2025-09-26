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
        elif self.service_tracking == 'event':
            # Auto-publish event products on website
            self.website_published = True

    def _get_event_info(self):
        """Get event information for display purposes"""
        self.ensure_one()
        if not self.event_id:
            return {}

        return {
            'event_name': self.event_id.name,
            'event_date_begin': self.event_id.date_begin,
            'event_date_end': self.event_id.date_end,
        }

    def _is_event_ticket_available(self):
        """Check if the event ticket is available for purchase"""
        self.ensure_one()
        # For product.template, check the first variant that has an event ticket
        variant = self.product_variant_ids.filtered('event_ticket_id')[:1]
        if not variant:
            return False

        return variant._is_event_ticket_available()

    @api.model
    def _get_saleable_tracking_types(self):
        """Extend saleable tracking types to include event products"""
        return super()._get_saleable_tracking_types() + ['event']
