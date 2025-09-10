# Website Event Ticket Store

This module allows event tickets to be purchased directly from the website store by storing event and ticket information directly on the product model.

## Problem Solved

When trying to purchase event tickets from the standard web store, you get the error:

> "The sale order line with the product VIP Ticket needs an event and a ticket."

This happens because event products require both `event_id` and `event_ticket_id` fields to be set, but the standard website store doesn't provide a way to select these when adding products to the cart.

## Solution

This module provides:

1. **Product-Level Configuration**: Adds `event_id` and `event_ticket_id` fields to `product.template` and `product.product` models, allowing admins to pre-configure which event and ticket each product represents.

2. **Automatic Field Population**: When a product is added to cart, the event and ticket fields are automatically populated from the product configuration.

3. **Integrated Website Display**: Event information (dates, availability, ticket details) is displayed directly on product pages and in the cart, integrated into the normal store interface.

4. **Validation**: Ensures products are properly configured and tickets are available before allowing purchase.

## Features

- **Admin Configuration**: Easy setup of event and ticket information on products
- **Automatic Population**: Event and ticket fields automatically set from product configuration
- **Website Integration**: Event information displayed on product pages, product lists, and cart
- **Availability Checking**: Real-time validation of ticket availability and event dates
- **Seamless Experience**: No separate pages or complex selection interfaces needed

## Installation

1. Place the module in your Odoo addons directory
2. Update the module list
3. Install the "Website Event Ticket Store" module

## Dependencies

- `website_sale`
- `event_sale`
- `website_event_sale`

## Usage

### For Administrators

1. **Create Event Products**: When creating a product with `service_tracking = 'event'`, configure the `event_id` and `event_ticket_id` fields
2. **Event Information**: The product will automatically display event dates, ticket details, and availability on the website
3. **Multiple Products**: Create separate products for different ticket types (VIP, Standard, etc.) of the same event

### For Customers

1. **Browse Products**: Event products show event information directly on product pages
2. **Add to Cart**: Normal "Add to Cart" functionality works seamlessly
3. **Cart Display**: Cart shows event and ticket information for each item
4. **Checkout**: Normal checkout process with all required fields populated

## Technical Details

### Models Extended

- `product.template`: Added event and ticket configuration fields
- `product.product`: Added event availability checking methods
- `sale.order.line`: Modified to auto-populate from product configuration
- `sale.order`: Enhanced cart validation for event products

### Views Created

- Product form views with event configuration fields
- Enhanced product templates showing event information
- Cart templates displaying event details
- Search filters for event products

## Configuration

1. **Create Events**: Set up your events in the Events app
2. **Create Event Tickets**: Configure ticket types for each event
3. **Create Products**: Create products with `service_tracking = 'event'` and select the appropriate event and ticket
4. **Publish Products**: Make products available on the website

## Testing

The module includes comprehensive tests covering:

- Product event configuration
- Automatic field population
- Cart update functionality
- Availability checking
- Onchange methods

Run tests with:

```bash
odoo-bin -d your_database -i website_event_ticket_store --test-enable
```

## Support

For issues or questions, please contact your system administrator or refer to the Odoo documentation.
