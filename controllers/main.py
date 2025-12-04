# -*- coding: utf-8 -*-

import json
from odoo import http, fields, _
from odoo.exceptions import ValidationError, AccessError
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class WebsiteEventTicketStore(WebsiteSale):
    """Extend website sale to handle event ticket attendee data"""

    def _check_cart_and_addresses(self, order_sudo):
        """Allow checkout to proceed without attendee collection - now handled after payment"""
        # Simply call parent method without redirecting to attendee collection
        return super()._check_cart_and_addresses(order_sudo)

    @http.route(['/shop/product/<model("product.template"):product>'], type='http', auth="public", website=True)
    def product(self, product, category='', search='', **kwargs):
        """Override product page to add event information"""
        result = super().product(product, category, search, **kwargs)

        # Add event information to the context
        if hasattr(result, 'qcontext') and product.service_tracking == 'event':
            result.qcontext['event_info'] = self._get_event_info_for_product(product)

        return result

    def _get_event_info_for_product(self, product):
        """Get event information for a product to display on the website"""
        if not product or product.service_tracking != 'event':
            return None

        if not product.event_id:
            return None

        # Get the first variant that has an event ticket
        variant = product.product_variant_ids.filtered('event_ticket_id')[:1]
        if not variant:
            return None

        return {
            'event_name': product.event_id.name,
            'event_date_begin': product.event_id.date_begin,
            'event_date_end': product.event_id.date_end,
            'ticket_name': variant.event_ticket_id.name,
            'ticket_price': variant.event_ticket_id.price,
            'ticket_price_reduce': variant.event_ticket_id.price_reduce,
            'seats_available': variant.event_ticket_id.seats_available if variant.event_ticket_id.seats_limited else None,
            'seats_limited': variant.event_ticket_id.seats_limited,
            'ticket_description': variant.event_ticket_id.description or '',
            'is_available': product._is_event_ticket_available(),
        }

    @http.route(['/shop/payment/validate'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_validate(self, sale_order_id=None, **post):
        """Override to redirect to attendee collection for event orders after payment"""
        if sale_order_id is None:
            order = request.website.sale_get_order()
            if not order and 'sale_last_order_id' in request.session:
                last_order_id = request.session['sale_last_order_id']
                order = request.env['sale.order'].sudo().browse(last_order_id).exists()
        else:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            assert order.id == request.session.get('sale_last_order_id')

        errors = self._get_shop_payment_errors(order)
        if errors:
            first_error = errors[0]
            error_msg = f"{first_error[0]}\n{first_error[1]}"
            raise ValidationError(error_msg)

        tx_sudo = order.get_portal_last_transaction() if order else order.env['payment.transaction']

        if not order or (order.amount_total and not tx_sudo):
            return request.redirect('/shop')

        if order and not order.amount_total and not tx_sudo:
            # Check if this is an event order that needs attendee collection (before validating)
            if order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event'):
                event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
                has_registrations = any(line.registration_ids for line in event_lines)

                if not has_registrations:
                    # Don't validate the order yet - we need attendee data first
                    # Generate access token for the order
                    token = order._generate_attendee_access_token()
                    # Send email reminder
                    self._send_attendee_details_reminder(order)
                    # Redirect to token-based URL (same flow as paid orders)
                    return request.redirect(order.get_attendee_details_url())

            # For non-event orders or orders with existing registrations, validate and proceed
            if order.state != 'sale':
                order._validate_order()

            request.website.sale_reset()
            return request.redirect(order.get_portal_url())

        # Check if this is an event order that needs attendee collection (for paid orders)
        if order and order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event'):
            event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
            has_registrations = any(line.registration_ids for line in event_lines)

            if not has_registrations:
                # Generate access token for the order
                token = order._generate_attendee_access_token()
                # Send email reminder
                self._send_attendee_details_reminder(order)
                # Redirect to token-based URL
                return request.redirect(order.get_attendee_details_url())

        # For non-event orders or orders with existing registrations, proceed normally
        request.website.sale_reset()
        if tx_sudo and tx_sudo.state == 'draft':
            return request.redirect('/shop')

        return request.redirect('/shop/confirmation')

    @http.route(['/shop/event_attendees_post_payment'], type='http', auth="public", methods=['GET', 'POST'], website=True, csrf=False)
    def event_attendees_post_payment(self, **kw):
        """Event attendee collection after payment confirmation - DEPRECATED, use token-based route"""
        # For backward compatibility, redirect to shop if no session order
        order_id = request.session.get('pending_attendee_order_id')
        if not order_id:
            return request.redirect('/shop')

        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return request.redirect('/shop')

        # Generate token and redirect to new URL
        token = order._generate_attendee_access_token()
        return request.redirect(order.get_attendee_details_url())

    @http.route(['/my/orders/<int:order_id>/attendee-details/<string:access_token>'], type='http', auth="public", methods=['GET', 'POST'], website=True, csrf=False)
    def order_attendee_details(self, order_id, access_token, **kw):
        """Token-based attendee collection page"""
        try:
            order = self._get_order_with_token(order_id, access_token)
        except (AccessError, ValidationError):
            return request.redirect('/shop')

        # Check if there are any event products in the order
        event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if not event_lines:
            return request.redirect('/shop/confirmation')

        # Enforce successful payment before attendee collection (or allow free orders)
        tx = order.get_portal_last_transaction()
        # Allow free orders (amount_total == 0) or orders with successful payment
        if order.amount_total > 0 and not (tx and tx.state in ['done', 'authorized']):
            # Put order in session and redirect to payment
            request.session['sale_order_id'] = order.id
            return request.redirect('/shop/payment')

        # Check if already completed
        has_registrations = any(line.registration_ids for line in event_lines)
        if has_registrations:
            # Already completed, redirect to order portal page
            return request.redirect(order.get_portal_url())

        if request.httprequest.method == 'POST':
            # Process attendee data and create registrations
            self._process_event_attendee_data_from_checkout(order, kw)

            # Now confirm the order since we have attendee data
            order.with_context(skip_attendee_validation=True).action_confirm()

            # If the order is paid and still 'to invoice', create and post the invoice now
            try:
                tx_check = order.get_portal_last_transaction()
                if order.invoice_status == 'to invoice' and tx_check and tx_check.state in ['done', 'authorized']:
                    invoices = order._create_invoices()
                    if invoices:
                        invoices.action_post()
            except Exception:
                # Avoid blocking the user flow; invoice can be generated manually if needed
                pass

            # Store the order ID for confirmation page
            request.session['sale_last_order_id'] = order.id
            # Redirect to final confirmation
            return request.redirect('/shop/confirmation')

        # Render the post-payment attendee collection page
        values = {
            'website_sale_order': order,
            'access_token': access_token,
        }
        return request.render('website_event_ticket_store.event_attendee_post_payment', values)

    def _get_order_with_token(self, order_id, access_token):
        """Get order and verify access token"""
        order = request.env['sale.order'].sudo().browse(order_id)

        if not order.exists():
            raise ValidationError(_('Order not found'))

        if not order.attendee_access_token or order.attendee_access_token != access_token:
            raise AccessError(_('Invalid access token'))

        return order

    def _send_attendee_details_reminder(self, order):
        """Send email reminder to complete attendee details"""
        template = request.env.ref('website_event_ticket_store.mail_template_attendee_details_reminder', raise_if_not_found=False)
        if template:
            template.sudo().send_mail(order.id, force_send=True, email_values={'email_to': order.partner_id.email})

    def _process_event_attendee_data_from_checkout(self, order, form_data):
        """Process attendee data from checkout step and create event registrations"""
        import logging
        _logger = logging.getLogger(__name__)

        _logger.info(f"Processing attendee data for order {order.id}")
        _logger.info(f"Form data keys: {list(form_data.keys())}")

        # Clear existing registrations for this order
        order.order_line.mapped('registration_ids').unlink()

        # Process each attendee
        attendee_counter = 1
        while f"{attendee_counter}-event_ticket_id" in form_data:
            event_ticket_id = form_data.get(f"{attendee_counter}-event_ticket_id")
            sale_order_line_id = form_data.get(f"{attendee_counter}-sale_order_line_id")

            _logger.info(f"Processing attendee {attendee_counter}: ticket_id={event_ticket_id}, line_id={sale_order_line_id}")

            if not event_ticket_id or not sale_order_line_id:
                _logger.warning(f"Missing data for attendee {attendee_counter}")
                attendee_counter += 1
                continue

            # Get the order line and event ticket
            order_line = request.env['sale.order.line'].browse(int(sale_order_line_id))
            event_ticket = request.env['event.event.ticket'].browse(int(event_ticket_id))

            if not order_line.exists() or not event_ticket.exists():
                _logger.warning(f"Order line or event ticket not found for attendee {attendee_counter}")
                attendee_counter += 1
                continue

            # Extract attendee data from event questions
            attendee_data = self._extract_attendee_data_from_questions(event_ticket.event_id, form_data, attendee_counter)
            _logger.info(f"Extracted attendee data: {attendee_data}")

            # If no attendee data was extracted from questions, try to get basic info from form
            if not attendee_data:
                # Try to get basic attendee info directly from form fields
                attendee_data = {
                    'name': form_data.get(f"{attendee_counter}-name", ''),
                    'email': form_data.get(f"{attendee_counter}-email", ''),
                    'phone': form_data.get(f"{attendee_counter}-phone", ''),
                    'company_name': form_data.get(f"{attendee_counter}-company_name", ''),
                }
                _logger.info(f"Using direct form data: {attendee_data}")

            # Create registration with extracted data
            vals = {
                'event_id': event_ticket.event_id.id,
                'event_ticket_id': event_ticket.id,
                'sale_order_id': order.id,
                'sale_order_line_id': order_line.id,
                'name': attendee_data.get('name', ''),
                'email': attendee_data.get('email', ''),
                'phone': attendee_data.get('phone', ''),
                'company_name': attendee_data.get('company_name', ''),
                'state': 'draft',
            }

            _logger.info(f"Creating registration with vals: {vals}")

            # Create registration
            registration = request.env['event.registration'].sudo().create(vals)
            _logger.info(f"Created registration: {registration.id}")

            # Process event question answers
            self._process_event_question_answers(event_ticket.event_id, form_data, registration, attendee_counter)

            attendee_counter += 1

    def _process_event_attendee_data(self, product, form_data, quantity):
        """Process attendee data from form and create event registrations (legacy method)"""

        # Get the current sale order
        sale_order = request.website.sale_get_order()
        if not sale_order:
            return

        # Find the sale order line for this product
        # Note: This method is legacy and may not work correctly with the new structure
        order_line = sale_order.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id == product
        )

        if not order_line:
            return

        # Extract attendee data from event questions
        attendee_data = self._extract_attendee_data_from_questions(product.event_id, form_data, 1)

        # Create registration with extracted data
        # Note: This method is legacy and may not work correctly with the new structure
        vals = {
            'event_id': product.event_id.id,
            'event_ticket_id': order_line.event_ticket_id.id if order_line.event_ticket_id else False,
            'sale_order_id': sale_order.id,
            'sale_order_line_id': order_line.id,
            'name': attendee_data.get('name', ''),
            'email': attendee_data.get('email', ''),
            'phone': attendee_data.get('phone', ''),
            'company_name': attendee_data.get('company_name', ''),
            'state': 'draft',
        }

        # Create registration
        registration = request.env['event.registration'].sudo().create(vals)

        # Process event question answers
        self._process_event_question_answers(product.event_id, form_data, registration, 1)

    def _extract_attendee_data_from_questions(self, event, form_data, attendee_counter=1):
        """Extract attendee data from event questions (name, email, phone, company)"""
        import logging
        _logger = logging.getLogger(__name__)

        attendee_data = {}

        _logger.info(f"Extracting data for event {event.id}, attendee {attendee_counter}")
        _logger.info(f"Event has {len(event.question_ids)} questions")

        if not event.question_ids:
            _logger.info("No event questions found")
            return attendee_data

        # Look for standard attendee fields in questions
        for question in event.question_ids:
            field_name = f"{attendee_counter}-{question.question_type}-{question.id}"
            answer_value = form_data.get(field_name, '').strip()

            _logger.info(f"Question {question.id} ({question.question_type}): field_name={field_name}, value='{answer_value}'")

            if not answer_value:
                continue

            # Map question types to attendee fields
            if question.question_type == 'name':
                attendee_data['name'] = answer_value
            elif question.question_type == 'email':
                attendee_data['email'] = answer_value
            elif question.question_type == 'phone':
                attendee_data['phone'] = answer_value
            elif question.question_type == 'company_name':
                attendee_data['company_name'] = answer_value

        _logger.info(f"Final attendee data: {attendee_data}")
        return attendee_data

    def _process_event_question_answers(self, event, form_data, registration, attendee_counter=1):
        """Process event question answers and create registration answers"""

        if not event.question_ids or not registration:
            return

        # Process each question
        for question in event.question_ids:
            field_name = f"{attendee_counter}-{question.question_type}-{question.id}"
            answer_value = form_data.get(field_name)

            if not answer_value:
                continue

            # Create registration answer
            answer_vals = {
                'registration_id': registration.id,
                'question_id': question.id,
            }

            if question.question_type == 'simple_choice':
                answer_vals['value_answer_id'] = int(answer_value)
            else:
                answer_vals['value_text_box'] = answer_value

            request.env['event.registration.answer'].sudo().create(answer_vals)


class EventTicketStorePortal(CustomerPortal):
    """Portal controller for event ticket store"""

    def _prepare_home_portal_values(self, counters):
        """Add pending event registrations counter to portal"""
        values = super()._prepare_home_portal_values(counters)

        if 'pending_event_registrations_count' in counters:
            # Count orders with pending attendee details
            partner = request.env.user.partner_id
            domain = [
                ('partner_id', '=', partner.id),
                ('state', 'in', ['draft', 'sent']),
            ]

            pending_count = 0
            orders = request.env['sale.order'].search(domain)
            for order in orders:
                if order._has_pending_attendee_details():
                    tx = order.get_portal_last_transaction()
                    if tx and tx.state in ['done', 'authorized']:
                        pending_count += 1

            values['pending_event_registrations_count'] = pending_count

        if 'event_registrations_count' in counters:
            partner = request.env.user.partner_id
            # Count all registrations related to user's orders
            registrations_domain = [
                ('sale_order_id.partner_id', '=', partner.id),
            ]
            values['event_registrations_count'] = request.env['event.registration'].sudo().search_count(registrations_domain)

        return values

    @http.route(['/my/pending-registrations'], type='http', auth="user", website=True)
    def portal_my_pending_registrations(self, **kw):
        """Display orders with pending attendee details"""
        partner = request.env.user.partner_id

        # Find all orders with pending attendee details
        domain = [
            ('partner_id', '=', partner.id),
            ('state', 'in', ['draft', 'sent']),
        ]

        orders = request.env['sale.order'].search(domain)
        pending_orders = request.env['sale.order']
        for o in orders:
            if o._has_pending_attendee_details():
                tx = o.get_portal_last_transaction()
                if tx and tx.state in ['done', 'authorized']:
                    pending_orders |= o

        values = {
            'pending_orders': pending_orders,
            'page_name': 'pending_registrations',
        }

        return request.render('website_event_ticket_store.portal_my_pending_registrations', values)

    @http.route(['/my/registrations'], type='http', auth="user", website=True)
    def portal_my_registrations(self, page=1, **kw):
        """Display all event registrations linked to customer's orders"""
        partner = request.env.user.partner_id
        Registration = request.env['event.registration']

        domain = [('sale_order_id.partner_id', '=', partner.id)]

        # Simple pager
        total = Registration.sudo().search_count(domain)
        step = 20
        pager = portal_pager(url='/my/registrations', total=total, page=page, step=step, scope=7)

        registrations = Registration.sudo().search(domain, order='create_date desc', limit=step, offset=pager['offset'])

        values = {
            'registrations': registrations,
            'page_name': 'event_registrations',
            'pager': pager,
        }
        return request.render('website_event_ticket_store.portal_my_registrations', values)
