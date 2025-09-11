# -*- coding: utf-8 -*-

import json
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteEventTicketStore(WebsiteSale):
    """Extend website sale to handle event ticket attendee data"""

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

        if not product.event_id or not product.event_ticket_id:
            return None

        return {
            'event_name': product.event_id.name,
            'event_date_begin': product.event_id.date_begin,
            'event_date_end': product.event_id.date_end,
            'ticket_name': product.event_ticket_id.name,
            'ticket_price': product.event_ticket_id.price,
            'ticket_price_reduce': product.event_ticket_id.price_reduce,
            'seats_available': product.event_ticket_id.seats_available if product.event_ticket_id.seats_limited else None,
            'seats_limited': product.event_ticket_id.seats_limited,
            'ticket_description': product.event_ticket_id.description or '',
            'is_available': product._is_event_ticket_available(),
        }

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """Override cart update to handle event attendee data"""

        # Check if this is an event product with attendee data
        product = request.env['product.product'].browse(int(product_id))

        if product.service_tracking == 'event' and product.event_id and product.event_ticket_id:
            # Process attendee data from form fields
            self._process_event_attendee_data(product, kw, add_qty)

        # Call parent method for normal cart update
        return super().cart_update(product_id, add_qty, set_qty, **kw)

    def _process_event_attendee_data(self, product, form_data, quantity):
        """Process attendee data from form and create event registrations"""

        # Get the current sale order
        sale_order = request.website.sale_get_order()
        if not sale_order:
            return

        # Find the sale order line for this product
        order_line = sale_order.order_line.filtered(
            lambda line: line.product_id == product and line.event_ticket_id == product.event_ticket_id
        )

        if not order_line:
            return

        # Extract attendee data from event questions
        attendee_data = self._extract_attendee_data_from_questions(product, form_data)

        # Create registration with extracted data
        vals = {
            'event_id': product.event_id.id,
            'event_ticket_id': product.event_ticket_id.id,
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
        self._process_event_question_answers(product, form_data, registration)

    def _extract_attendee_data_from_questions(self, product, form_data):
        """Extract attendee data from event questions (name, email, phone, company)"""

        attendee_data = {}

        if not product.event_id.question_ids:
            return attendee_data

        # Look for standard attendee fields in questions
        for question in product.event_id.question_ids:
            field_name = f"1-{question.question_type}-{question.id}"
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

    def _process_event_question_answers(self, product, form_data, registration):
        """Process event question answers and create registration answers"""

        if not product.event_id.question_ids or not registration:
            return

        # Process each question
        for question in product.event_id.question_ids:
            field_name = f"1-{question.question_type}-{question.id}"
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
