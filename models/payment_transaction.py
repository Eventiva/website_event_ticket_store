# -*- coding: utf-8 -*-

from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _check_amount_and_confirm_order(self):
        """Override to handle event orders - auto-generate attendee registrations from billing details"""
        confirmed_orders = self.env['sale.order']
        for tx in self:
            # We only support the flow where exactly one quotation is linked to a transaction.
            if len(tx.sale_order_ids) == 1:
                quotation = tx.sale_order_ids.filtered(lambda so: so.state in ('draft', 'sent'))
                if quotation and quotation._is_confirmation_amount_reached():
                    # Check if this is an event order without attendee data
                    if quotation._portal_event_order_lines():
                        event_lines = quotation._portal_event_order_lines()
                        has_registrations = any(line.registration_ids for line in event_lines)

                        if not has_registrations:
                            # Auto-generate attendee registrations from billing details
                            quotation._auto_generate_attendee_registrations()

                    # Proceed with confirmation (registrations are now auto-generated if needed)
                    quotation.with_context(send_email=True).action_confirm()
                    confirmed_orders |= quotation
        return confirmed_orders

