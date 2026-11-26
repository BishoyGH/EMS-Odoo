from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ems_loa_governing_law = fields.Char('Governing Law', config_parameter='ems.loa.governing_law')
    ems_loa_forum = fields.Char('Forum', config_parameter='ems.loa.forum')
    ems_loa_liability_cap = fields.Char('Liability Cap', config_parameter='ems.loa.liability_cap')
    ems_loa_insurance = fields.Char('Insurance', config_parameter='ems.loa.insurance')
    ems_loa_delay_damages = fields.Char('Delay Damages', config_parameter='ems.loa.delay_damages')
