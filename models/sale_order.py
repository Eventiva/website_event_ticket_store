# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Override to handle event ticket validation and ensure event fields are set"""
        self.ensure_one()

        # Check if this is an event product
        product = self.env['product.product'].browse(product_id)
        if product.service_tracking == 'event':
            # Validate that the product has event and ticket configured
            if not product.product_tmpl_id.event_id or not product.event_ticket_id:
                raise UserError(_(
                    "This event product is not properly configured. "
                    "Please contact the administrator to set up the event and ticket information."
                ))

            # Check if the event ticket is available
            if not product._is_event_ticket_available():
                raise UserError(_(
                    "This event ticket is no longer available for purchase. "
                    "The event may be sold out or expired."
                ))

            # For event products, we need to ensure the event fields are set
            # We'll do this by calling the parent method and then updating the line
            result = super()._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

            # After the line is created/updated, ensure event fields are set
            if line_id:
                # Updating existing line
                line = self.order_line.filtered(lambda l: l.id == line_id)
            else:
                # New line - find the most recently created line for this product
                line = self.order_line.filtered(lambda l: l.product_id.id == product_id)[-1:]

            if line and line.product_id.service_tracking == 'event':
                line.write({
                    'event_id': product.product_tmpl_id.event_id.id,
                    'event_ticket_id': product.event_ticket_id.id,
                })

            return result

        return super()._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

    def _prepare_order_line_values(self, product_id, quantity, event_ticket_id=False, **kwargs):
        """Override to set event fields for our variant-based architecture"""
        values = super()._prepare_order_line_values(product_id, quantity, event_ticket_id, **kwargs)

        # If this is an event product and we have a variant with event_ticket_id
        product = self.env['product.product'].browse(product_id)
        if product.service_tracking == 'event' and product.event_ticket_id:
            # Set the event fields from our variant
            values['event_id'] = product.product_tmpl_id.event_id.id
            values['event_ticket_id'] = product.event_ticket_id.id

        return values

    def action_confirm(self):
        """Override to validate event attendee data before confirmation"""
        # Check if there are event products in this order
        event_lines = self.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if event_lines:
            # Check if attendee data has been collected
            has_registrations = any(line.registration_ids for line in event_lines)
            if not has_registrations:
                raise UserError(_(
                    "Event attendee details must be collected before confirming this order. "
                    "Please complete the attendee registration process."
                ))

        return super().action_confirm()

