# -*- coding: utf-8 -*-

import json
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteEventTicketStore(WebsiteSale):
    """Extend website sale to handle event ticket attendee data"""

    def _check_cart_and_addresses(self, order_sudo):
        """Override to redirect to attendee collection for event products"""
        # First check the parent method
        redirection = super()._check_cart_and_addresses(order_sudo)
        if redirection:
            return redirection

        # Check if there are event products in the cart
        if order_sudo and order_sudo.order_line.filtered(lambda line: line.product_id.service_tracking == 'event'):
            # Check if we're already on the attendee page to avoid infinite redirect
            if request.httprequest.path != '/shop/event_attendees':
                # Debug logging
                import logging
                _logger = logging.getLogger(__name__)
                _logger.info(f"Redirecting to attendee collection for order {order_sudo.id}")
                # Redirect to attendee collection page
                return request.redirect('/shop/event_attendees')

        return redirection

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

    @http.route(['/shop/event_attendees'], type='http', auth="public", methods=['GET', 'POST'], website=True, csrf=False)
    def event_attendees(self, **kw):
        """Event attendee collection step in checkout process"""
        order = request.website.sale_get_order()

        if not order:
            return request.redirect('/shop/cart')

        # Check if there are any event products in the cart
        event_lines = order.order_line.filtered(lambda line: line.product_id.service_tracking == 'event')
        if not event_lines:
            return request.redirect('/shop/checkout')

        if request.httprequest.method == 'POST':
            # Process attendee data and create registrations
            self._process_event_attendee_data_from_checkout(order, kw)
            return request.redirect('/shop/checkout')

        # Render the attendee collection page
        values = {
            'website_sale_order': order,
        }
        return request.render('website_event_ticket_store.event_attendee_checkout', values)

    def _process_event_attendee_data_from_checkout(self, order, form_data):
        """Process attendee data from checkout step and create event registrations"""

        # Clear existing registrations for this order
        order.order_line.mapped('registration_ids').unlink()

        # Process each attendee
        attendee_counter = 1
        while f"{attendee_counter}-event_ticket_id" in form_data:
            event_ticket_id = form_data.get(f"{attendee_counter}-event_ticket_id")
            sale_order_line_id = form_data.get(f"{attendee_counter}-sale_order_line_id")

            if not event_ticket_id or not sale_order_line_id:
                attendee_counter += 1
                continue

            # Get the order line and event ticket
            order_line = request.env['sale.order.line'].browse(int(sale_order_line_id))
            event_ticket = request.env['event.event.ticket'].browse(int(event_ticket_id))

            if not order_line.exists() or not event_ticket.exists():
                attendee_counter += 1
                continue

            # Extract attendee data from event questions
            attendee_data = self._extract_attendee_data_from_questions(event_ticket.event_id, form_data, attendee_counter)

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

            # Create registration
            registration = request.env['event.registration'].sudo().create(vals)

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

        attendee_data = {}

        if not event.question_ids:
            return attendee_data

        # Look for standard attendee fields in questions
        for question in event.question_ids:
            field_name = f"{attendee_counter}-{question.question_type}-{question.id}"
            answer_value = form_data.get(field_name, '').strip()

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
