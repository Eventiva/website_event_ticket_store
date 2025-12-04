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

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure event fields are set for event products"""
        # Ensure event fields are set for event products before creation
        for vals in vals_list:
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product and product.service_tracking == 'event':
                    # Set event fields from product before validation runs
                    if 'event_id' not in vals:
                        vals['event_id'] = product.product_tmpl_id.event_id.id if product.product_tmpl_id.event_id else False
                    if 'event_ticket_id' not in vals:
                        vals['event_ticket_id'] = product.event_ticket_id.id if product.event_ticket_id else False
                else:
                    # Clear event fields for non-event products
                    if 'event_id' not in vals:
                        vals['event_id'] = False
                    if 'event_ticket_id' not in vals:
                        vals['event_ticket_id'] = False
        return super().create(vals_list)

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

    def write(self, values):
        """Override write to ensure event fields are set for event products before validation"""
        # Skip this logic if we're already fixing event fields (to prevent recursion)
        if self.env.context.get('skip_event_field_setting'):
            return super().write(values)
        
        # If product_id is being set/changed, ensure event fields are set for event products
        if 'product_id' in values:
            product = self.env['product.product'].browse(values['product_id'])
            if product and product.service_tracking == 'event':
                # Set event fields from product before validation runs
                # Only set if not already in values (to allow manual override)
                if 'event_id' not in values:
                    values['event_id'] = product.product_tmpl_id.event_id.id if product.product_tmpl_id.event_id else False
                if 'event_ticket_id' not in values:
                    values['event_ticket_id'] = product.event_ticket_id.id if product.event_ticket_id else False
            else:
                # Clear event fields for non-event products
                if 'event_id' not in values:
                    values['event_id'] = False
                if 'event_ticket_id' not in values:
                    values['event_ticket_id'] = False
        
        # Also check existing records that might have product_id but missing event fields
        # This handles cases where loyalty system writes to lines without setting product_id
        # We need to set these fields before validation runs in super().write()
        records_to_fix = []
        for record in self:
            if record.product_id and record.product_id.service_tracking == 'event':
                if not record.event_id or not record.event_ticket_id:
                    records_to_fix.append(record)
        
        # Fix records that need event fields set (before calling super().write)
        # Write to each record individually to set the fields before validation
        # Use context flag to prevent recursion
        if records_to_fix:
            for record in records_to_fix:
                record.with_context(skip_event_field_setting=True).write({
                    'event_id': record.product_id.product_tmpl_id.event_id.id if record.product_id.product_tmpl_id.event_id else False,
                    'event_ticket_id': record.product_id.event_ticket_id.id if record.product_id.event_ticket_id else False,
                })
        
        return super().write(values)

    def _get_display_price(self):
        """Override to use product/variant price instead of event ticket price"""
        if self.event_ticket_id and self.event_id:
            # For event tickets, use the product's price instead of the event ticket price
            # This allows product pricing, discounts, and attribute pricing to work correctly
            # Implement the original sale.order.line logic directly to bypass event_sale override
            self.ensure_one()

            if self.product_type == 'combo':
                return 0  # The display price of a combo line should always be 0.
            if self.combo_item_id:
                return self._get_combo_item_display_price()

            # Use the original pricing logic without event ticket override
            pricelist_price = self._get_pricelist_price()

            if not self.pricelist_item_id._show_discount():
                # No pricelist rule found => no discount from pricelist
                return pricelist_price

            base_price = self._get_pricelist_price_before_discount()

            # negative discounts (= surcharge) are included in the display price
            return max(base_price, pricelist_price)

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
