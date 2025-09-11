# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Override to handle event ticket validation and attendee collection"""
        self.ensure_one()

        # Check if this is an event product
        product = self.env['product.product'].browse(product_id)
        if product.service_tracking == 'event':
            # Validate that the product has event and ticket configured
            if not product.event_id or not product.event_ticket_id:
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

            # Pass the event_ticket_id to the parent method so website_event_sale
            # knows we're adding a new ticket rather than increasing quantity
            kwargs['event_ticket_id'] = product.event_ticket_id.id

        # Perform the cart update
        result = super()._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

        # If this is an event product and we're adding tickets (not removing),
        # trigger the attendee information collection
        if (product.service_tracking == 'event' and
            product.event_id and product.event_ticket_id and
            (add_qty > 0 or set_qty > 0)):

            # Check if we need to collect attendee information
            if self._should_collect_attendee_info(product_id, add_qty, set_qty):
                # Return the registration editor action instead of normal cart update result
                return self._get_registration_editor_action()

        return result

    def _should_collect_attendee_info(self, product_id, add_qty, set_qty):
        """Determine if we need to collect attendee information for this cart update"""
        # Only collect attendee info when adding new tickets, not when removing
        if add_qty > 0 or set_qty > 0:
            # Check if this is a new line or if we're adding to an existing line
            existing_line = self.order_line.filtered(
                lambda l: l.product_id.id == product_id and l.event_ticket_id
            )
            if not existing_line:
                # This is a new event ticket line, collect attendee info
                return True
            elif add_qty > 0:
                # We're adding more tickets to an existing line, collect attendee info for new ones
                return True
        return False

    def _get_registration_editor_action(self):
        """Return the registration editor action to collect attendee information"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'registration.editor',
            'view_mode': 'form',
            'view_id': self.env.ref('website_event_ticket_store.view_event_registration_editor_cart_form').id,
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'from_cart': True,  # Flag to indicate this came from cart
            }
        }

    def _prepare_order_line_values(self, product_id, quantity, **kwargs):
        """Override to automatically set event ticket values from product"""
        # For event products, we need to handle the ticket matching differently
        product = self.env['product.product'].browse(product_id)
        if product.service_tracking == 'event' and product.event_id and product.event_ticket_id:
            # Skip the website_event_sale validation by calling the base sale.order method
            values = super(SaleOrder, self)._prepare_order_line_values(product_id, quantity, **kwargs)
            values.update({
                'event_id': product.event_id.id,
                'event_ticket_id': product.event_ticket_id.id,
            })
        else:
            # For non-event products, use the normal flow including website_event_sale
            values = super()._prepare_order_line_values(product_id, quantity, **kwargs)

        return values
