from odoo import fields, models


class EmsLoaClause(models.Model):
    _name = 'ems.loa.clause'
    _description = 'Standard LOA Clause'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    title = fields.Char(required=True)
    body = fields.Html(required=True)
    active = fields.Boolean(default=True)
