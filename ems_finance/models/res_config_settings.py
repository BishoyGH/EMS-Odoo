from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ems_overhead_pct = fields.Float(
        'Overhead allocation %', config_parameter='ems.overhead_pct',
        help='Optional overhead as % of contracted revenue. Margin is always shown before and after overhead.')
