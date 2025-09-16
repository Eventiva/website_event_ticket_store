# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Website(models.Model):
    _inherit = 'website'

    def _get_checkout_step_list(self):
        """Add event attendee collection step to checkout process"""
        steps = super()._get_checkout_step_list()

        # Check if there are event products in the current cart
        order = self.sale_get_order()
        if order and order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event'):
            # Insert event attendee step after cart review but before checkout
            event_attendee_step = (['website_event_ticket_store.event_attendee_checkout'], {
                'name': 'Event Attendees',
                'current_href': '/shop/event_attendees',
                'main_button': 'Continue to Payment',
                'main_button_href': '/shop/checkout',
                'back_button': 'Back to Cart',
                'back_button_href': '/shop/cart',
            })

            # Find the position after cart step
            cart_index = next((i for i, (xmlids, _) in enumerate(steps) if 'website_sale.cart' in xmlids), -1)
            if cart_index >= 0:
                steps.insert(cart_index + 1, event_attendee_step)
            else:
                # If cart step not found, add at the beginning
                steps.insert(0, event_attendee_step)

        return steps
