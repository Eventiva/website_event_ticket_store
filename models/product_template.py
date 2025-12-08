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

    def _get_combination_info(self, combination=None, product_id=None, add_qty=1, parent_combination=None, only_template=None, **kwargs):
        """Override to ensure combo products have a valid price"""
        # Odoo 19 doesn't accept parent_combination as a keyword argument
        # Pass it through kwargs if provided
        if parent_combination is not None:
            kwargs['parent_combination'] = parent_combination
        info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            only_template=only_template,
            **kwargs
        )
        
        # Ensure combo products have a valid price in the result
        # For combo products, if price is 0/None, use list_price as fallback
        # This allows the configurator to open even before combo items are selected
        # Check if this is a combo product - use self.type since we're in product.template
        if self.type == 'combo' and (not info.get('price') or info.get('price') == 0):
            # Use list_price as the base price for combo products
            if product_id:
                product = self.env['product.product'].browse(product_id)
                info['price'] = product.list_price or 0
            else:
                # Fallback to template's list_price if no product_id
                info['price'] = self.list_price or 0
        
        return info
