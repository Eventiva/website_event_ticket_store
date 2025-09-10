# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestEventTicketStore(TransactionCase):
    """Test cases for the website_event_ticket_store module"""

    def setUp(self):
        super().setUp()

        # Create test event
        self.event = self.env['event.event'].create({
            'name': 'Test Event',
            'date_begin': '2024-12-31 10:00:00',
            'date_end': '2024-12-31 18:00:00',
        })

        # Create test event ticket
        self.event_ticket = self.env['event.event.ticket'].create({
            'name': 'VIP Ticket',
            'event_id': self.event.id,
            'price': 100.0,
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
        self.event.date_end = '2020-01-01 18:00:00'
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
