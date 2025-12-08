# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def cleanup_problematic_views(self):
        """
        Remove views with problematic XPath expressions that no longer work in Odoo 19.
        This method can be called during module upgrade to clean up old views.
        Specifically removes views with XPath: //form[@t-if='is_add_to_cart_possible']
        which no longer works because the form structure changed in Odoo 19.
        """
        problematic_patterns = [
            "form[@t-if='is_add_to_cart_possible'",
            "form[@t-if=\"is_add_to_cart_possible\"",
        ]
        
        views_to_remove = self.env['ir.ui.view']
        
        # Search for views that contain the problematic XPath pattern
        # We search for a partial match since the exact format may vary
        for pattern in problematic_patterns:
            # Escape special characters for SQL LIKE
            search_pattern = pattern.replace('[', r'[').replace(']', r']').replace("'", r"'")
            matching_views = self.search([
                ('arch_db', 'ilike', search_pattern),
            ])
            views_to_remove |= matching_views
        
        # Also check views that inherit from website_sale.product
        # as they're most likely to have this issue
        product_inherit_views = self.search([
            ('inherit_id', '!=', False),
        ])
        
        for view in product_inherit_views:
            # Check if this view inherits from website_sale.product
            if view.inherit_id and 'website_sale.product' in (view.inherit_id.key or ''):
                arch = view.arch_db or ''
                for pattern in problematic_patterns:
                    if pattern in arch:
                        _logger.warning(
                            "Found problematic view '%s' (ID: %s) inheriting from website_sale.product with pattern: %s",
                            view.name, view.id, pattern
                        )
                        views_to_remove |= view
                        break
        
        if views_to_remove:
            view_names = ', '.join([v.name for v in views_to_remove])
            _logger.info("Removing %d problematic view(s): %s", len(views_to_remove), view_names)
            views_to_remove.unlink()
            return len(views_to_remove)
        
        _logger.info("No problematic views found to remove")
        return 0

