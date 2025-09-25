# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class EventEvent(models.Model):
    _inherit = 'event.event'

    # Store redirect options
    redirect_to_store = fields.Boolean(
        string='Redirect Register Button to Store',
        help="When enabled, the 'Register' button on the event page will redirect to the store page instead of the normal registration flow.",
        default=False
    )

    store_product_template_id = fields.Many2one(
        'product.template',
        string='Store Product Template',
        help="The product template to redirect to when 'Redirect to Store' is enabled. If not set, will redirect to the general store page.",
        domain=[('service_tracking', '=', 'event')]
    )

    @api.onchange('redirect_to_store')
    def _onchange_redirect_to_store(self):
        """Clear store product when redirect is disabled"""
        if not self.redirect_to_store:
            self.store_product_template_id = False

    def get_store_redirect_url(self):
        """Get the URL to redirect to for store registration"""
        self.ensure_one()
        if not self.redirect_to_store:
            return False

        if self.store_product_template_id:
            return f'/shop/product/{self.store_product_template_id.id}'
        else:
            return '/shop'

    def action_view_store_products(self):
        """Action to view store products for this event"""
        self.ensure_one()
        return {
            'name': _('Store Products for %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'tree,form',
            'domain': [('service_tracking', '=', 'event'), ('event_id', '=', self.id)],
            'context': {
                'default_service_tracking': 'event',
                'default_event_id': self.id,
            }
        }
