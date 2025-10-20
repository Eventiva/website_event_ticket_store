# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import uuid
import logging


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    attendee_access_token = fields.Char(
        string='Attendee Details Access Token',
        copy=False,
        help='Token to access the attendee details page after payment'
    )

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
        # Skip validation if we're confirming after attendee data collection
        if self.env.context.get('skip_attendee_validation'):
            return super().action_confirm()

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

    def _validate_order(self):
        """Override to handle event orders that need attendee data collection"""
        # For event orders without attendee data, don't validate yet
        event_lines = self.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if event_lines:
            has_registrations = any(line.registration_ids for line in event_lines)
            if not has_registrations:
                # Don't validate event orders without attendee data
                # The order will be validated after attendee collection
                return

        # For non-event orders or event orders with attendee data, proceed normally
        super()._validate_order()

    def _generate_attendee_access_token(self):
        """Generate a unique access token for attendee details page"""
        self.ensure_one()
        if not self.attendee_access_token:
            self.attendee_access_token = str(uuid.uuid4())
        return self.attendee_access_token

    def _has_pending_attendee_details(self):
        """Check if this order has event tickets without attendee registrations"""
        self.ensure_one()
        event_lines = self.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if not event_lines:
            return False
        has_registrations = any(line.registration_ids for line in event_lines)
        return not has_registrations and self.state in ('draft', 'sent')

    def get_attendee_details_url(self):
        """Get the URL to complete attendee details"""
        self.ensure_one()
        if not self.attendee_access_token:
            self._generate_attendee_access_token()
        base_url = self.get_base_url()
        return f"{base_url}/my/orders/{self.id}/attendee-details/{self.attendee_access_token}"

    def action_send_attendee_details_reminder(self):
        """Manual action to send attendee details reminder email"""
        for order in self:
            if order._has_pending_attendee_details():
                # Generate token if it doesn't exist
                if not order.attendee_access_token:
                    order._generate_attendee_access_token()

                # Send the reminder email
                template = self.env.ref('website_event_ticket_store.mail_template_attendee_details_reminder', raise_if_not_found=False)
                if template:
                    template.send_mail(order.id, force_send=True, email_values={'email_to': order.partner_id.email})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reminder Sent'),
                'message': _('Attendee details reminder email(s) have been sent.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_send_pending_attendee_reminders(self):
        """Scheduled action to send reminders for orders with pending attendee details

        This finds orders that:
        - Have event products
        - Have successful payment (transaction in 'done' state)
        - Don't have attendee registrations yet
        - Are in draft/sent state
        - Haven't received a reminder in the last 24 hours (optional)
        """
        # Find orders with pending attendee details
        domain = [
            ('state', 'in', ['draft', 'sent']),
            ('order_line.product_id.service_tracking', '=', 'event'),
        ]

        orders = self.search(domain)
        orders_to_remind = self.env['sale.order']

        for order in orders:
            # Check if this order has pending attendee details
            if order._has_pending_attendee_details():
                # Check if there's a successful payment transaction
                tx = order.get_portal_last_transaction()
                if tx and tx.state in ['done', 'authorized']:
                    # Generate token if missing
                    if not order.attendee_access_token:
                        order._generate_attendee_access_token()
                    orders_to_remind |= order

        # Send reminder emails
        template = self.env.ref('website_event_ticket_store.mail_template_attendee_details_reminder', raise_if_not_found=False)
        if template:
            for order in orders_to_remind:
                template.send_mail(order.id, force_send=False, email_values={'email_to': order.partner_id.email})

        _logger = logging.getLogger(__name__)
        _logger.info(f'Sent {len(orders_to_remind)} attendee details reminder emails')

        return True

    @api.model
    def action_fix_legacy_pending_orders(self):
        """Admin utility to find and fix orders created before token system

        This identifies orders that:
        - Have event products
        - Have successful payment
        - Don't have attendee details
        - Don't have tokens (legacy orders)

        And generates tokens + sends reminder emails
        """
        domain = [
            ('state', 'in', ['draft', 'sent']),
            ('order_line.product_id.service_tracking', '=', 'event'),
            ('attendee_access_token', '=', False),  # No token yet
        ]

        legacy_orders = self.search(domain)
        fixed_orders = self.env['sale.order']

        for order in legacy_orders:
            if order._has_pending_attendee_details():
                # Check if there's a successful payment
                tx = order.get_portal_last_transaction()
                if tx and tx.state in ['done', 'authorized']:
                    # Generate token
                    order._generate_attendee_access_token()
                    fixed_orders |= order

        # Send reminder emails for all fixed orders
        template = self.env.ref('website_event_ticket_store.mail_template_attendee_details_reminder', raise_if_not_found=False)
        if template:
            for order in fixed_orders:
                template.send_mail(order.id, force_send=True, email_values={'email_to': order.partner_id.email})

        _logger = logging.getLogger(__name__)
        _logger.info(f'Fixed {len(fixed_orders)} legacy orders without tokens')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Legacy Orders Fixed'),
                'message': _(f'{len(fixed_orders)} order(s) have been processed and reminder emails sent.'),
                'type': 'success',
                'sticky': False,
            }
        }

