# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Website(models.Model):
    _inherit = 'website'

    def _get_checkout_step_list(self):
        """Remove event attendee collection from checkout process - now handled after payment"""
        # Simply return the parent steps without adding attendee collection
        return super()._get_checkout_step_list()
