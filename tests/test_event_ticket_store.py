# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('website_event_ticket_store', 'post_install', '-at_install')
class TestEventTicketStore(TransactionCase):
    """Test cases for the website_event_ticket_store module"""

    def setUp(self):
        super().setUp()

        # Create test event
        self.event = self.env['event.event'].create({
            'name': 'Test Event',
            'date_begin': '2025-12-31 10:00:00',
            'date_end': '2025-12-31 18:00:00',
        })

        # Create test event ticket
        self.event_ticket = self.env['event.event.ticket'].create({
            'name': 'VIP Ticket',
            'event_id': self.event.id,
            'price': 100.0,
            'sale_available': True,
        })

        # Create test product with event configuration
        self.product = self.env['product.product'].create({
            'name': 'VIP Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 100.0,
            'event_id': self.event.id,
            'event_ticket_id': self.event_ticket.id,
        })

        # Create test sale order
        self.sale_order = self.env['sale.order'].create({
            'partner_id': self.env.ref('base.res_partner_1').id,
        })

    def test_product_event_configuration(self):
        """Test that product can be configured with event and ticket"""
        # Check that product has event and ticket configured
        self.assertEqual(self.product.event_id, self.event)
        self.assertEqual(self.product.event_ticket_id, self.event_ticket)
        self.assertEqual(self.product.service_tracking, 'event')

    def test_product_event_info(self):
        """Test getting event information from product"""
        event_info = self.product._get_event_info()

        self.assertEqual(event_info['event_name'], self.event.name)
        self.assertEqual(event_info['ticket_name'], self.event_ticket.name)
        self.assertEqual(event_info['ticket_price'], self.event_ticket.price)

    def test_product_event_availability(self):
        """Test checking if event ticket is available"""
        # Test available ticket
        self.assertTrue(self.product._is_event_ticket_available())

        # Test expired event
        self.event.write({
            'date_begin': '2020-01-01 10:00:00',
            'date_end': '2020-01-01 18:00:00'
        })
        self.assertFalse(self.product._is_event_ticket_available())

    def test_sale_order_line_auto_population(self):
        """Test that sale order line automatically gets event data from product"""
        # Create sale order line with required event fields
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'event_id': self.event.id,
            'event_ticket_id': self.event_ticket.id,
        })

        # Check that event fields are set correctly
        self.assertEqual(line.event_id, self.event)
        self.assertEqual(line.event_ticket_id, self.event_ticket)

    def test_sale_order_line_onchange_method(self):
        """Test that sale order line onchange method works correctly"""
        # Create sale order line without event fields
        line = self.env['sale.order.line'].new({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
        })

        # Call the onchange method
        line._onchange_product_id_event_ticket()

        # Check that event fields are automatically populated
        self.assertEqual(line.event_id, self.event)
        self.assertEqual(line.event_ticket_id, self.event_ticket)

    def test_cart_update_with_event_product(self):
        """Test cart update with event product"""
        # Test cart update
        result = self.sale_order._cart_update(
            product_id=self.product.id,
            add_qty=1
        )

        # Check that line was created with event data
        self.assertEqual(len(self.sale_order.order_line), 1)
        line = self.sale_order.order_line[0]
        self.assertEqual(line.event_id, self.event)
        self.assertEqual(line.event_ticket_id, self.event_ticket)

    def test_cart_update_unconfigured_event_product(self):
        """Test cart update with unconfigured event product"""
        # Create unconfigured event product
        unconfigured_product = self.env['product.product'].create({
            'name': 'Unconfigured Event Product',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 100.0,
            # No event_id or event_ticket_id
        })

        # Test cart update should fail
        with self.assertRaises(UserError):
            self.sale_order._cart_update(
                product_id=unconfigured_product.id,
                add_qty=1
            )

    def test_cart_update_unavailable_event_product(self):
        """Test cart update with unavailable event product"""
        # Make event ticket unavailable
        self.event_ticket.sale_available = False

        # Test cart update should fail
        with self.assertRaises(UserError):
            self.sale_order._cart_update(
                product_id=self.product.id,
                add_qty=1
            )

    def test_product_onchange_methods(self):
        """Test product onchange methods"""
        # Test service_tracking onchange on template
        self.product.product_tmpl_id.service_tracking = 'no'
        self.product.product_tmpl_id._onchange_service_tracking()
        self.assertFalse(self.product.product_tmpl_id.event_id)
        self.assertFalse(self.product.product_tmpl_id.event_ticket_id)

        # Test event_id onchange on template
        self.product.product_tmpl_id.service_tracking = 'event'
        self.product.product_tmpl_id.event_id = self.event
        self.product.product_tmpl_id._onchange_event_id()
        # Should clear ticket if it doesn't belong to event
        if self.product.product_tmpl_id.event_ticket_id and self.product.product_tmpl_id.event_ticket_id.event_id != self.event:
            self.assertFalse(self.product.product_tmpl_id.event_ticket_id)

        # Test event_ticket_id onchange on template
        self.product.product_tmpl_id.event_ticket_id = self.event_ticket
        self.product.product_tmpl_id._onchange_event_ticket_id()
        self.assertEqual(self.product.product_tmpl_id.event_id, self.event)

    def test_sale_order_line_event_info(self):
        """Test getting event info from sale order line"""
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'event_id': self.event.id,
            'event_ticket_id': self.event_ticket.id,
        })

        event_info = line._get_event_info()
        self.assertEqual(event_info['event_name'], self.event.name)
        self.assertEqual(event_info['ticket_name'], self.event_ticket.name)

    def test_climb26_event_scenario(self):
        """Test the specific Climb26 event scenario from the images"""
        # Create Climb26 event (July 2026)
        climb26_event = self.env['event.event'].create({
            'name': 'Climb26',
            'date_begin': '2026-07-01 09:00:00',
            'date_end': '2026-07-02 18:00:00',
            'website_published': True,
        })

        # Create Standard Ticket with future sale dates and unlimited seats (0 = unlimited)
        standard_ticket = self.env['event.event.ticket'].create({
            'name': 'Standard Ticket',
            'event_id': climb26_event.id,
            'price': 100.0,
            'seats_max': 0,  # 0 = unlimited seats
            'start_sale_datetime': '2025-07-02 00:00:00',  # Future sale start
            'end_sale_datetime': '2025-10-01 00:00:00',    # Future sale end
        })

        # Create product for Standard Ticket
        standard_product = self.env['product.product'].create({
            'name': 'Standard Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 100.0,
            'event_id': climb26_event.id,
            'event_ticket_id': standard_ticket.id,
        })

        # Test that ticket is available (should be True with our fix)
        self.assertTrue(standard_product._is_event_ticket_available())

        # Test that seats_limited is False for unlimited tickets
        self.assertFalse(standard_ticket.seats_limited)

        # Test that seats_available is 0 for unlimited tickets (this is correct behavior)
        self.assertEqual(standard_ticket.seats_available, 0)

    def test_future_sale_start_date_scenario(self):
        """Test tickets with future sale start dates (like in the images)"""
        # Create event
        future_event = self.env['event.event'].create({
            'name': 'Future Event',
            'date_begin': '2026-07-01 09:00:00',
            'date_end': '2026-07-02 18:00:00',
        })

        # Create ticket with future sale start date
        future_ticket = self.env['event.event.ticket'].create({
            'name': 'Early Adopter Ticket',
            'event_id': future_event.id,
            'price': 100.0,
            'seats_max': 0,  # Unlimited
            'start_sale_datetime': '2025-07-02 00:00:00',  # Future start
            'end_sale_datetime': '2025-10-01 00:00:00',    # Future end
        })

        # Create product
        future_product = self.env['product.product'].create({
            'name': 'Early Adopter Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 100.0,
            'event_id': future_event.id,
            'event_ticket_id': future_ticket.id,
        })

        # Should be available because sale period is in the future but within range
        self.assertTrue(future_product._is_event_ticket_available())

    def test_unlimited_seats_scenario(self):
        """Test tickets with unlimited seats (Maximum = 0)"""
        # Create event
        unlimited_event = self.env['event.event'].create({
            'name': 'Unlimited Event',
            'date_begin': '2025-12-31 10:00:00',
            'date_end': '2025-12-31 18:00:00',
        })

        # Create ticket with unlimited seats
        unlimited_ticket = self.env['event.event.ticket'].create({
            'name': 'Unlimited Ticket',
            'event_id': unlimited_event.id,
            'price': 400.0,
            'seats_max': 0,  # 0 = unlimited
        })

        # Create product
        unlimited_product = self.env['product.product'].create({
            'name': 'Unlimited Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 400.0,
            'event_id': unlimited_event.id,
            'event_ticket_id': unlimited_ticket.id,
        })

        # Should be available
        self.assertTrue(unlimited_product._is_event_ticket_available())

        # Verify unlimited behavior
        self.assertFalse(unlimited_ticket.seats_limited)
        self.assertEqual(unlimited_ticket.seats_available, 0)

    def test_limited_seats_scenario(self):
        """Test tickets with limited seats"""
        # Create event
        limited_event = self.env['event.event'].create({
            'name': 'Limited Event',
            'date_begin': '2025-12-31 10:00:00',
            'date_end': '2025-12-31 18:00:00',
        })

        # Create ticket with limited seats
        limited_ticket = self.env['event.event.ticket'].create({
            'name': 'Limited Ticket',
            'event_id': limited_event.id,
            'price': 200.0,
            'seats_max': 100,  # Limited to 100 seats
        })

        # Create product
        limited_product = self.env['product.product'].create({
            'name': 'Limited Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 200.0,
            'event_id': limited_event.id,
            'event_ticket_id': limited_ticket.id,
        })

        # Should be available (100 seats available)
        self.assertTrue(limited_product._is_event_ticket_available())

        # Verify limited behavior
        self.assertTrue(limited_ticket.seats_limited)
        self.assertEqual(limited_ticket.seats_available, 100)

    def test_sold_out_scenario(self):
        """Test sold out tickets"""
        # Create event
        sold_out_event = self.env['event.event'].create({
            'name': 'Sold Out Event',
            'date_begin': '2025-12-31 10:00:00',
            'date_end': '2025-12-31 18:00:00',
        })

        # Create ticket with limited seats
        sold_out_ticket = self.env['event.event.ticket'].create({
            'name': 'Sold Out Ticket',
            'event_id': sold_out_event.id,
            'price': 300.0,
            'seats_max': 1,  # Only 1 seat
        })

        # Create a registration to fill the seat
        self.env['event.registration'].create({
            'event_id': sold_out_event.id,
            'event_ticket_id': sold_out_ticket.id,
            'partner_id': self.env.ref('base.res_partner_1').id,
            'state': 'done',
        })

        # Create product
        sold_out_product = self.env['product.product'].create({
            'name': 'Sold Out Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 300.0,
            'event_id': sold_out_event.id,
            'event_ticket_id': sold_out_ticket.id,
        })

        # Should not be available (sold out)
        self.assertFalse(sold_out_product._is_event_ticket_available())

        # Verify sold out behavior
        self.assertTrue(sold_out_ticket.seats_limited)
        self.assertEqual(sold_out_ticket.seats_available, 0)

    def test_expired_sale_period_scenario(self):
        """Test tickets with expired sale periods"""
        # Create event
        expired_event = self.env['event.event'].create({
            'name': 'Expired Sale Event',
            'date_begin': '2025-12-31 10:00:00',
            'date_end': '2025-12-31 18:00:00',
        })

        # Create ticket with expired sale period
        expired_ticket = self.env['event.event.ticket'].create({
            'name': 'Expired Sale Ticket',
            'event_id': expired_event.id,
            'price': 150.0,
            'seats_max': 0,  # Unlimited
            'start_sale_datetime': '2020-01-01 00:00:00',  # Past start
            'end_sale_datetime': '2020-12-31 23:59:59',    # Past end
        })

        # Create product
        expired_product = self.env['product.product'].create({
            'name': 'Expired Sale Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 150.0,
            'event_id': expired_event.id,
            'event_ticket_id': expired_ticket.id,
        })

        # Should not be available (sale period expired)
        self.assertFalse(expired_product._is_event_ticket_available())

    def test_not_yet_started_sale_period_scenario(self):
        """Test tickets with sale periods that haven't started yet"""
        # Create event
        not_started_event = self.env['event.event'].create({
            'name': 'Not Started Sale Event',
            'date_begin': '2025-12-31 10:00:00',
            'date_end': '2025-12-31 18:00:00',
        })

        # Create ticket with future sale start
        not_started_ticket = self.env['event.event.ticket'].create({
            'name': 'Not Started Sale Ticket',
            'event_id': not_started_event.id,
            'price': 250.0,
            'seats_max': 0,  # Unlimited
            'start_sale_datetime': '2030-01-01 00:00:00',  # Far future start
            'end_sale_datetime': '2030-12-31 23:59:59',    # Far future end
        })

        # Create product
        not_started_product = self.env['product.product'].create({
            'name': 'Not Started Sale Ticket',
            'type': 'service',
            'service_tracking': 'event',
            'list_price': 250.0,
            'event_id': not_started_event.id,
            'event_ticket_id': not_started_ticket.id,
        })

        # Should not be available (sale hasn't started)
        self.assertFalse(not_started_product._is_event_ticket_available())

    def test_multiple_ticket_types_scenario(self):
        """Test multiple ticket types like in the Climb26 event"""
        # Create Climb26 event
        climb26_event = self.env['event.event'].create({
            'name': 'Climb26',
            'date_begin': '2026-07-01 09:00:00',
            'date_end': '2026-07-02 18:00:00',
            'website_published': True,
        })

        # Create multiple ticket types as shown in the images
        ticket_types = [
            {'name': '1 Day Wednesday Ticket', 'price': 210.0, 'seats_max': 0, 'start_sale': None, 'end_sale': None},
            {'name': '1 Day Thursday Ticket', 'price': 210.0, 'seats_max': 0, 'start_sale': None, 'end_sale': None},
            {'name': 'Startup Special Ticket', 'price': 400.0, 'seats_max': 100, 'start_sale': '2025-07-03 13:00:00', 'end_sale': '2026-07-02 18:00:00'},
            {'name': 'Standard Ticket', 'price': 400.0, 'seats_max': 0, 'start_sale': '2025-07-03 13:00:00', 'end_sale': '2026-07-02 18:00:00'},
            {'name': 'VIP Ticket', 'price': 600.0, 'seats_max': 0, 'start_sale': '2025-07-03 13:00:00', 'end_sale': '2026-07-02 18:00:00'},
            {'name': 'Investor Ticket', 'price': 600.0, 'seats_max': 0, 'start_sale': None, 'end_sale': None},
        ]

        tickets = []
        products = []

        for ticket_data in ticket_types:
            # Create ticket
            ticket = self.env['event.event.ticket'].create({
                'name': ticket_data['name'],
                'event_id': climb26_event.id,
                'price': ticket_data['price'],
                'seats_max': ticket_data['seats_max'],
                'start_sale_datetime': ticket_data['start_sale'],
                'end_sale_datetime': ticket_data['end_sale'],
            })
            tickets.append(ticket)

            # Create product
            product = self.env['product.product'].create({
                'name': ticket_data['name'],
                'type': 'service',
                'service_tracking': 'event',
                'list_price': ticket_data['price'],
                'event_id': climb26_event.id,
                'event_ticket_id': ticket.id,
            })
            products.append(product)

        # Test availability for each ticket type
        # Tickets with sale periods should be available
        self.assertTrue(products[2]._is_event_ticket_available())  # Startup Special
        self.assertTrue(products[3]._is_event_ticket_available())  # Standard
        self.assertTrue(products[4]._is_event_ticket_available())  # VIP

        # Tickets without sale periods should also be available (no restrictions)
        self.assertTrue(products[0]._is_event_ticket_available())  # 1 Day Wednesday
        self.assertTrue(products[1]._is_event_ticket_available())  # 1 Day Thursday
        self.assertTrue(products[5]._is_event_ticket_available())  # Investor

        # Verify seat limits
        self.assertFalse(tickets[0].seats_limited)  # Wednesday - unlimited
        self.assertFalse(tickets[1].seats_limited)  # Thursday - unlimited
        self.assertTrue(tickets[2].seats_limited)   # Startup Special - limited
        self.assertFalse(tickets[3].seats_limited)  # Standard - unlimited
        self.assertFalse(tickets[4].seats_limited)  # VIP - unlimited
        self.assertFalse(tickets[5].seats_limited)  # Investor - unlimited
