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
- **Post-Payment Attendee Collection**: Collects attendee details after successful payment
- **Token-Based Access**: Secure, resumable attendee details forms accessible via unique tokens
- **Email Reminders**: Automatic email sent with link to complete attendee details
- **Portal Integration**: Pending registrations displayed in customer portal with alerts
- **Persistent Access**: Users can always return to complete their attendee details

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
5. **Payment**: Complete payment for event tickets
6. **Attendee Details**: After payment, provide details for each attendee
   - Redirected automatically to attendee details page
   - Receive email with secure link to the form
   - Can close and return later using the link
7. **Portal Access**: View pending registrations in "My Account" portal
   - Alert banner if attendee details are pending
   - "Pending Event Registrations" page lists all incomplete orders
   - One-click access to complete any pending details

## Technical Details

### Models Extended

- `product.template`: Added event and ticket configuration fields
- `product.product`: Added event availability checking methods
- `sale.order.line`: Modified to auto-populate from product configuration
- `sale.order`: Enhanced cart validation for event products, added token-based attendee access
  - `attendee_access_token`: Secure token field for accessing attendee details
  - `_generate_attendee_access_token()`: Generates unique access tokens
  - `_has_pending_attendee_details()`: Checks if order needs attendee information
  - `get_attendee_details_url()`: Returns secure URL to complete attendee details

### Controllers

- `WebsiteEventTicketStore`: Handles shop flow and redirects to attendee collection
  - Token-based route: `/my/orders/<order_id>/attendee-details/<token>`
  - Secure access validation
  - Automatic email sending after payment
- `EventTicketStorePortal`: Portal integration for pending registrations
  - Route: `/my/pending-registrations`
  - Counter integration on portal home page

### Views Created

- Product form views with event configuration fields
- Enhanced product templates showing event information
- Cart templates displaying event details
- Search filters for event products
- Post-payment attendee collection form
- Portal page for pending registrations
- Portal banner alerting users to pending details

### Email Templates

- `mail_template_attendee_details_reminder`: Sent after payment with secure access link
  - Includes order summary
  - Provides persistent access link
  - Explains completion process

## Configuration

1. **Create Events**: Set up your events in the Events app
2. **Create Event Tickets**: Configure ticket types for each event
3. **Create Products**: Create products with `service_tracking = 'event'` and select the appropriate event and ticket
4. **Publish Products**: Make products available on the website
5. **Email Template**: The attendee details reminder email is automatically configured
   - Customize at Settings > Technical > Email Templates
   - Search for "Event Ticket: Complete Attendee Details"

## Attendee Details Flow

### Payment-to-Registration Process

1. **Customer Completes Payment**: After successful payment processing
2. **Token Generation**: System generates unique access token for the order
3. **Email Sent**: Customer receives email with secure link
4. **Redirect**: Customer automatically redirected to attendee details page
5. **Form Completion**: Customer fills in details for each ticket holder
6. **Order Confirmation**: Order is confirmed once all attendee details submitted

### Recovery Options

If a customer closes the attendee details page:

1. **Email Link**: Click the link in the reminder email (always accessible)
2. **Portal Access**: Log in to "My Account" portal
   - Alert banner shows if pending details exist
   - "Pending Event Registrations" page lists incomplete orders
   - Click "Complete Attendee Details" on any pending order
3. **Session Persistence**: Token-based access works across sessions and devices

### Security

- Each order gets a unique UUID token
- Token required to access attendee details page
- Only order partner can access via portal
- Email link works for guest checkouts
- Tokens stored securely in database

## Migration & Legacy Order Handling

### Handling Pre-Token Orders

If you're upgrading from a version without the token system, you may have orders that:
- Successfully took payment
- Are waiting for attendee details
- Don't have access tokens yet

### Automatic Token Generation

The system automatically generates tokens for legacy orders when needed:
- When customer accesses the old session-based URL
- During the scheduled reminder job
- When admin uses the "Send Attendee Details Reminder" button

### Manual Admin Actions

#### 1. Fix Legacy Orders (Bulk Action)

**Location**: Sales > Orders > Select orders > Action > "Generate Tokens for Legacy Event Orders"

**What it does**:
- Finds orders in draft/sent state
- With event products
- With successful payment
- Without tokens
- Generates tokens and sends reminder emails

**Usage**:
1. Go to Sales > Orders
2. Filter for orders in draft/sent state
3. Select multiple orders (or use no selection for all)
4. Click "Action" dropdown
5. Select "Generate Tokens for Legacy Event Orders"

#### 2. Send Individual Reminder

**Location**: Sales > Orders > Open order > "Send Attendee Details Reminder" button

**What it does**:
- Checks if order has pending attendee details
- Generates token if missing
- Sends reminder email immediately

**Usage**:
1. Open any order with pending attendee details
2. Click "Send Attendee Details Reminder" in header
3. Customer receives email with access link

#### 3. View Pending Orders

**Location**: Sales > Configuration > Event Ticket Store > Pending Attendee Details

**What it shows**:
- All orders with generated tokens
- Waiting for attendee details
- Allows bulk operations

### Automated Reminders

**Scheduled Action**: Event Ticket Store: Send Attendee Details Reminders

**Default**: Disabled (enable as needed)

**Frequency**: Daily (configurable)

**What it does**:
1. Finds all orders with pending attendee details
2. Checks for successful payment transactions
3. Generates tokens if missing
4. Sends reminder emails

**To Enable**:
1. Go to Settings > Technical > Automation > Scheduled Actions
2. Search for "Event Ticket Store: Send Attendee Details Reminders"
3. Edit and set "Active" to true
4. Configure interval as needed (default: 1 day)

### Migration Steps

When upgrading to this version:

1. **Immediately after upgrade**: Run the bulk action to fix legacy orders
   ```
   Sales > Orders > Action > Generate Tokens for Legacy Event Orders
   ```

2. **Enable scheduled reminders** (optional but recommended):
   ```
   Settings > Technical > Automation > Scheduled Actions
   Search: "Event Ticket Store: Send Attendee Details Reminders"
   Set Active = True
   ```

3. **Verify**: Check "Pending Attendee Details" menu to see all orders awaiting completion

4. **Customer Communication**: Customers with pending orders will automatically receive emails

### Troubleshooting

**Problem**: Customer says they didn't receive the email

**Solution**:
1. Open the order in Sales > Orders
2. Click "Send Attendee Details Reminder" button
3. Or manually copy the URL: Go to order > Note the token in "Attendee Details Access Token" field
4. Share URL: `https://yoursite.com/my/orders/{ORDER_ID}/attendee-details/{TOKEN}`

**Problem**: Customer lost the email link

**Solution**:
1. They can log in to My Account portal
2. Banner will show pending registrations
3. Or click "Pending Event Registrations" menu
4. Or admin can resend using "Send Attendee Details Reminder"

## Admin Features

### Backend Actions

1. **Send Attendee Details Reminder Button**:
   - Visible on order form for draft/sent orders
   - Generates token if missing
   - Sends email immediately

2. **Smart Button**:
   - Shows "Attendee Details Pending" warning
   - Click to send reminder
   - Only visible when applicable

3. **Pending Attendee Details Menu**:
   - Lists all orders awaiting completion
   - Accessible via Sales > Configuration > Event Ticket Store
   - Supports bulk actions

## Testing

The module includes comprehensive tests covering:

- Product event configuration
- Automatic field population
- Cart update functionality
- Availability checking
- Onchange methods
- Post-payment attendee collection
- Token generation and validation

Run tests with:

```bash
odoo-bin -d your_database -i website_event_ticket_store --test-enable
```

## Support

For issues or questions, please contact your system administrator or refer to the Odoo documentation.
