from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ems_code = fields.Char('EMS Code', copy=False)
    ems_grade_id = fields.Many2one('ems.grade', string='Grade')
    ems_employment_type = fields.Selection([
        ('full', 'Full time'), ('part', 'Part time'),
        ('contract', 'Contractor'), ('freelance', 'Freelancer'),
    ], string='Employment Type', default='full')
    ems_hours_week = fields.Float('Capacity (h/week)', default=40.0)
    ems_plannable = fields.Boolean('Plannable', default=True,
                                   help='Shown in the planner and utilisation reports.')
    ems_date_start = fields.Date('Joined')
    ems_date_end = fields.Date('Left')
    ems_cost_rate = fields.Float('Cost Rate Override / h', groups='ems_base.group_ems_rates',
                                 help='Leave empty to use the grade cost rate.')
    ems_bank = fields.Char('Bank', groups='ems_base.group_ems_rates')
    ems_iban = fields.Char('IBAN', groups='ems_base.group_ems_rates')
    ems_mol = fields.Char('MOL Person Code', groups='ems_base.group_ems_rates')
    ems_notes = fields.Text('EMS Notes')

    def _ems_cost_per_hour(self):
        """Internal cost rate: override first, then grade. Needs the rates group."""
        self.ensure_one()
        return self.sudo().ems_cost_rate or self.sudo().ems_grade_id.cost_rate or 0.0

    ems_document_ids = fields.One2many(
        'ems.document', 'res_id', string='Documents', domain=[('res_model', '=', 'hr.employee')])
