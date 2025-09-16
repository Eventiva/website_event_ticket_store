# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        """Override to handle event ticket validation"""
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

        return super()._cart_update(product_id, line_id, add_qty, set_qty, **kwargs)

    def _prepare_order_line_values(self, product_id, quantity, **kwargs):
        """Override to handle product variants with event tickets"""
        # Get the event_ticket_id from kwargs if provided
        event_ticket_id = kwargs.get('event_ticket_id')

        if not event_ticket_id:
            return super()._prepare_order_line_values(product_id, quantity, **kwargs)

        ticket = self.env['event.event.ticket'].browse(event_ticket_id)
        product = self.env['product.product'].browse(product_id)

        # Enhanced validation: Allow product variants to work with the same event ticket
        # Check if the product is a variant of the ticket's product or matches exactly
        if (ticket.product_id.id != product_id and
            ticket.product_id.product_tmpl_id.id != product.product_tmpl_id.id):
            raise UserError(_(
                "The ticket doesn't match with this product. "
                "The product must be the same as the ticket's product or a variant of it."
            ))

        # Bypass website_event_sale validation by calling the base sale.order method directly
        # This avoids the strict product_id validation in website_event_sale
        values = super(SaleOrder, self)._prepare_order_line_values(product_id, quantity, **kwargs)

        # Add event-specific values
        values.update({
            'event_id': ticket.event_id.id,
            'event_ticket_id': ticket.id,
            'product_id': product_id,  # Use the variant product_id for the line
        })

        return values

    def _verify_updated_quantity(self, order_line, product_id, new_qty, event_ticket_id=False, **kwargs):
        """Override to handle product variants in quantity verification"""
        if not event_ticket_id:
            return super()._verify_updated_quantity(order_line, product_id, new_qty, **kwargs)

        ticket = self.env['event.event.ticket'].browse(event_ticket_id)
        product = self.env['product.product'].browse(product_id)

        # Enhanced validation: Allow product variants
        if (ticket.product_id.id != product_id and
            ticket.product_id.product_tmpl_id.id != product.product_tmpl_id.id):
            raise UserError(_(
                "The ticket doesn't match with this product. "
                "The product must be the same as the ticket's product or a variant of it."
            ))

        # Bypass website_event_sale validation by calling the base sale.order method directly
        # This avoids the strict product_id validation in website_event_sale
        return super(SaleOrder, self)._verify_updated_quantity(order_line, product_id, new_qty, **kwargs)
