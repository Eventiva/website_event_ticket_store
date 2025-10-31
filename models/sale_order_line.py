# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    @api.constrains('event_id', 'event_ticket_id', 'product_id')
    def _check_event_registration_ticket(self):
        """Override validation to skip reward lines - they don't need event fields immediately"""
        for so_line in self:
            # Skip validation for reward lines (coupon/discount lines)
            # These are discount lines and event details will be collected after payment
            # Check reward_id directly since is_reward_line is computed and may not be available during validation
            if so_line.reward_id or so_line.is_reward_line:
                continue

            # For regular order lines, enforce the validation
            if so_line.product_id.service_tracking == "event" and (not so_line.event_id or not so_line.event_ticket_id):
                raise ValidationError(
                    _("The sale order line with the product %(product_name)s needs an event and a ticket.",
                      product_name=so_line.product_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set event fields for reward lines with event products"""
        # Set event fields for reward lines if they're event products
        for vals in vals_list:
            if vals.get('is_reward_line') or vals.get('reward_id'):
                product_id = vals.get('product_id')
                if product_id:
                    product = self.env['product.product'].browse(product_id)
                    if product.service_tracking == 'event':
                        # Set event fields from product configuration for reward lines
                        if not vals.get('event_id') and product.product_tmpl_id.event_id:
                            vals['event_id'] = product.product_tmpl_id.event_id.id
                        if not vals.get('event_ticket_id') and product.event_ticket_id:
                            vals['event_ticket_id'] = product.event_ticket_id.id

        return super().create(vals_list)

    def write(self, vals):
        """Override write to set event fields for reward lines when product is updated"""
        # If updating product_id on reward lines, set event fields
        if 'product_id' in vals:
            # Check if any of the records being written are reward lines
            is_reward_line = vals.get('is_reward_line') or vals.get('reward_id') or any(self.mapped('is_reward_line')) or any(self.mapped('reward_id'))
            if is_reward_line:
                product = self.env['product.product'].browse(vals['product_id'])
                if product.service_tracking == 'event':
                    # Set event fields from product configuration for reward lines
                    if 'event_id' not in vals and product.product_tmpl_id.event_id:
                        vals['event_id'] = product.product_tmpl_id.event_id.id
                    if 'event_ticket_id' not in vals and product.event_ticket_id:
                        vals['event_ticket_id'] = product.event_ticket_id.id

        return super().write(vals)

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
