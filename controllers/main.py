# -*- coding: utf-8 -*-

import json
from odoo import http, fields, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


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
            if order.state != 'sale':
                order._validate_order()
            request.website.sale_reset()
            return request.redirect(order.get_portal_url())

        # Check if this is an event order that needs attendee collection
        if order and order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event'):
            event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
            has_registrations = any(line.registration_ids for line in event_lines)

            if not has_registrations:
                # Store the order ID in session for attendee collection
                request.session['pending_attendee_order_id'] = order.id
                # Don't reset the session yet - we need the order data for attendee collection
                # request.website.sale_reset()  # Comment this out temporarily
                return request.redirect('/shop/event_attendees_post_payment')

        # For non-event orders or orders with existing registrations, proceed normally
        request.website.sale_reset()
        if tx_sudo and tx_sudo.state == 'draft':
            return request.redirect('/shop')

        return request.redirect('/shop/confirmation')

    @http.route(['/shop/event_attendees_post_payment'], type='http', auth="public", methods=['GET', 'POST'], website=True, csrf=False)
    def event_attendees_post_payment(self, **kw):
        """Event attendee collection after payment confirmation"""
        # Get the order from session
        order_id = request.session.get('pending_attendee_order_id')
        if not order_id:
            return request.redirect('/shop')

        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return request.redirect('/shop')

        # Check if there are any event products in the order
        event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if not event_lines:
            return request.redirect('/shop/confirmation')

        if request.httprequest.method == 'POST':
            # Process attendee data and create registrations
            self._process_event_attendee_data_from_checkout(order, kw)

            # Now confirm the order since we have attendee data
            order.with_context(skip_attendee_validation=True).action_confirm()

            # Clear the pending order from session
            request.session.pop('pending_attendee_order_id', None)
            # Store the order ID for confirmation page
            request.session['sale_last_order_id'] = order.id
            # Reset the website sale session to clean up cart data
            request.website.sale_reset()
            # Redirect to final confirmation
            return request.redirect('/shop/confirmation')

        # Render the post-payment attendee collection page
        values = {
            'website_sale_order': order,
        }
        return request.render('website_event_ticket_store.event_attendee_post_payment', values)

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
