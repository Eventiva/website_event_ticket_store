# -*- coding: utf-8 -*-

from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _check_amount_and_confirm_order(self):
        """Override to handle event orders differently - don't auto-confirm if attendee data is missing"""
        confirmed_orders = self.env['sale.order']
        for tx in self:
            # We only support the flow where exactly one quotation is linked to a transaction.
            if len(tx.sale_order_ids) == 1:
                quotation = tx.sale_order_ids.filtered(lambda so: so.state in ('draft', 'sent'))
                if quotation and quotation._is_confirmation_amount_reached():
                    # Check if this is an event order without attendee data
                    if quotation.order_line.filtered(lambda line: line.product_id.service_tracking == 'event'):
                        event_lines = quotation.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
                        has_registrations = any(line.registration_ids for line in event_lines)

                        if not has_registrations:
                            # Don't auto-confirm event orders without attendee data
                            # The order will be confirmed later after attendee collection
                            continue

                    # For non-event orders or event orders with attendee data, proceed normally
                    quotation.with_context(send_email=True).action_confirm()
                    confirmed_orders |= quotation
        return confirmed_orders

