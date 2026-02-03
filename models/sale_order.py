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
    attendee_details_completed = fields.Boolean(
        string='Attendee Details Completed',
        default=False,
        help='Indicates if the attendee details have been completed/updated by the customer'
    )

    def _verify_updated_quantity(
        self, order_line, product_id, new_qty, uom_id, *, event_slot_id=False, event_ticket_id=False, **kwargs
    ):
        """Allow increasing event ticket quantity in cart (bypass website_event_sale restriction).

        When updating an existing event ticket line from the cart (no event_ticket_id in kwargs),
        website_event_sale blocks any quantity increase. For the ticket store we allow it by
        passing the line's event_ticket_id/event_slot_id so the parent runs seat availability
        checks but allows the new quantity.
        """
        if (
            order_line
            and order_line.event_ticket_id
            and not event_ticket_id
            and new_qty >= order_line.product_uom_qty
        ):
            # Cart is updating quantity on an event ticket line; pass ticket/slot so parent
            # allows the increase and still runs seat availability checks.
            event_slot_id = event_slot_id or (
                order_line.event_slot_id.id if getattr(order_line, 'event_slot_id', None) else False
            )
            event_ticket_id = order_line.event_ticket_id.id
        return super()._verify_updated_quantity(
            order_line,
            product_id,
            new_qty,
            uom_id,
            event_slot_id=event_slot_id,
            event_ticket_id=event_ticket_id,
            **kwargs,
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
                # Auto-generate attendee registrations from billing details
                self._auto_generate_attendee_registrations()

        # Call parent to confirm order (this may set registrations to 'open' in standard Odoo)
        result = super().action_confirm()

        # After confirmation, if attendee details are not completed, keep registrations as 'draft'
        # This ensures auto-generated registrations stay as 'draft' until the form is submitted
        if event_lines and not self.attendee_details_completed:
            all_registrations = event_lines.mapped('registration_ids')
            if all_registrations:
                # Set all registrations back to 'draft' if attendee details not completed
                all_registrations.sudo().write({'state': 'draft'})

        return result

    def _auto_generate_attendee_registrations(self):
        """Auto-generate attendee registrations from billing user details

        Uses the billing partner information to create registrations:
        - First attendee: Uses billing details directly
        - Additional attendees: Appends "Guest 1", "Guest 2", etc. to the name
        """
        self.ensure_one()

        # Get event order lines
        event_lines = self.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if not event_lines:
            return

        # Check if registrations already exist
        has_registrations = any(line.registration_ids for line in event_lines)
        if has_registrations:
            return

        # Set attendee details as not completed and generate access token
        self.attendee_details_completed = False
        self._generate_attendee_access_token()

        # Get billing partner details
        partner = self.partner_id
        billing_name = partner.name or ''
        billing_email = partner.email if partner.email else None
        # Safely get phone - check if mobile field exists first
        billing_phone = None
        if partner.phone:
            billing_phone = partner.phone
        elif hasattr(partner, 'mobile') and partner.mobile:
            billing_phone = partner.mobile
        billing_company = partner.commercial_partner_id.name if partner.commercial_partner_id else None

        _logger = logging.getLogger(__name__)
        _logger.info(f"Auto-generating attendee registrations for order {self.id} from billing partner {partner.id}")

        # Process each event line
        for order_line in event_lines:
            if not order_line.event_id or not order_line.event_ticket_id:
                continue

            # Get quantity for this line
            quantity = int(order_line.product_uom_qty)

            # Create one registration per quantity
            for attendee_num in range(quantity):
                # First attendee uses billing name directly, others append "Guest N"
                if attendee_num == 0:
                    attendee_name = billing_name
                else:
                    attendee_name = f"{billing_name} Guest {attendee_num}"

                # Create registration - only include fields if they exist
                registration_vals = {
                    'event_id': order_line.event_id.id,
                    'event_ticket_id': order_line.event_ticket_id.id,
                    'sale_order_id': self.id,
                    'sale_order_line_id': order_line.id,
                    'name': attendee_name,
                    'state': 'draft',
                }

                # Only add email if it exists
                if billing_email:
                    registration_vals['email'] = billing_email

                # Only add phone if it exists
                if billing_phone:
                    registration_vals['phone'] = billing_phone

                # Only add company_name if it exists
                if billing_company:
                    registration_vals['company_name'] = billing_company

                _logger.info(f"Creating registration {attendee_num + 1} for line {order_line.id}: {attendee_name}")
                self.env['event.registration'].sudo().create(registration_vals)

    def _generate_attendee_access_token(self):
        """Generate a unique access token for attendee details page"""
        self.ensure_one()
        if not self.attendee_access_token:
            self.attendee_access_token = str(uuid.uuid4())
        return self.attendee_access_token

    def _has_pending_attendee_details(self):
        """Check if this order has event tickets with incomplete attendee details"""
        self.ensure_one()
        event_lines = self.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if not event_lines:
            return False
        # Pending if attendee details are not completed and order is in draft/sent state
        return not self.attendee_details_completed and self.state in ('draft', 'sent')

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
        - Have attendee_details_completed = False
        - Are in draft/sent state
        - Haven't received a reminder in the last 24 hours (optional)
        """
        # Find orders with pending attendee details
        domain = [
            ('state', 'in', ['draft', 'sent']),
            ('order_line.product_id.service_tracking', '=', 'event'),
            ('attendee_details_completed', '=', False),
        ]

        orders = self.search(domain)
        orders_to_remind = self.env['sale.order']

        for order in orders:
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
        - Have attendee_details_completed = False
        - Don't have tokens (legacy orders)

        And generates tokens + sends reminder emails
        """
        domain = [
            ('state', 'in', ['draft', 'sent']),
            ('order_line.product_id.service_tracking', '=', 'event'),
            ('attendee_details_completed', '=', False),
            ('attendee_access_token', '=', False),  # No token yet
        ]

        legacy_orders = self.search(domain)
        fixed_orders = self.env['sale.order']

        for order in legacy_orders:
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

    def action_fix_and_confirm_unconfirmed_event_orders(self):
        """Admin utility to fix and confirm historic orders with payment but missing attendee details

        This identifies orders that:
        - Have event products
        - Have successful payment
        - Are in draft/sent state (not confirmed)
        - Have attendee_details_completed = False

        And:
        - Auto-generates attendee registrations from billing details
        - Confirms the orders
        """
        # If called from a specific record(s), use those; otherwise search for all matching orders
        if self:
            # Filter to only include orders that match the criteria
            unconfirmed_orders = self.filtered(lambda o: (
                o.state in ('draft', 'sent') and
                o.order_line.filtered(lambda l: l.product_id.service_tracking == 'event') and
                not o.attendee_details_completed
            ))
        else:
            domain = [
                ('state', 'in', ['draft', 'sent']),
                ('order_line.product_id.service_tracking', '=', 'event'),
                ('attendee_details_completed', '=', False),
            ]
            unconfirmed_orders = self.search(domain)

        fixed_orders = self.env['sale.order']
        confirmed_orders = self.env['sale.order']

        for order in unconfirmed_orders:
            # Check if there's a successful payment transaction
            tx = order.get_portal_last_transaction()
            if tx and tx.state in ['done', 'authorized']:
                # Auto-generate attendee registrations from billing details
                order._auto_generate_attendee_registrations()
                fixed_orders |= order

                # Confirm the order if it has registrations now
                event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
                has_registrations = any(line.registration_ids for line in event_lines)
                if has_registrations:
                    try:
                        order.with_context(skip_attendee_validation=True).action_confirm()
                        confirmed_orders |= order
                    except Exception as e:
                        _logger = logging.getLogger(__name__)
                        _logger.error(f'Failed to confirm order {order.id}: {str(e)}')

        _logger = logging.getLogger(__name__)
        _logger.info(f'Fixed and confirmed {len(confirmed_orders)} historic orders')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Historic Orders Fixed'),
                'message': _(f'{len(confirmed_orders)} order(s) have been fixed and confirmed. {len(fixed_orders) - len(confirmed_orders)} order(s) were processed but could not be confirmed.'),
                'type': 'success' if confirmed_orders else 'warning',
                'sticky': False,
            }
        }

