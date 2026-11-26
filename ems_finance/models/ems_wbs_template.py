from odoo import fields, models


class EmsWbsTemplate(models.Model):
    """The P0-P7 delivery template from the functional specification."""
    _name = 'ems.wbs.template'
    _description = 'WBS Template Stage'
    _order = 'sequence, code'

    code = fields.Char(required=True)
    name = fields.Char('Delivery Task / Acceptance', required=True)
    gate = fields.Char('Gate / Deliverable')
    sequence = fields.Integer(default=10)
    budget_pct = fields.Float('Budget Hours %', help='Share of the project delivery hours planned on this stage.')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'WBS code must be unique.')
