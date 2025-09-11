# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class RegistrationEditor(models.Model):
    _inherit = 'registration.editor'

    from_cart = fields.Boolean('From Cart', default=False)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res['from_cart'] = self._context.get('from_cart', False)
        return res

    def action_make_registration(self):
        """Override to handle cart flow differently"""
        self.ensure_one()

        # Call the parent method to create registrations
        result = super().action_make_registration()

        # If this came from cart, redirect back to cart instead of closing
        if self.from_cart:
            return {
                'type': 'ir.actions.act_url',
                'url': '/shop/cart',
                'target': 'self',
            }

        return result
