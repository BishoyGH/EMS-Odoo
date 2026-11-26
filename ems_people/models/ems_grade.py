from odoo import fields, models


class EmsGrade(models.Model):
    _name = 'ems.grade'
    _description = 'EMS Grade'
    _order = 'sequence, code'

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    cost_rate = fields.Monetary('Internal Cost / h', groups='ems_base.group_ems_rates')
    charge_rate = fields.Monetary('Charge-out Rate / h', groups='ems_base.group_ems_rates')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Grade code must be unique.')
