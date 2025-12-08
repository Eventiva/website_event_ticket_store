# -*- coding: utf-8 -*-

def post_init_hook(cr, registry):
    """
    Post-init hook to clean up problematic views after module upgrade.
    This removes views with XPath expressions that no longer work in Odoo 19.
    """
    env = registry(cr.dbname).env
    env['ir.ui.view'].cleanup_problematic_views()
    cr.commit()

