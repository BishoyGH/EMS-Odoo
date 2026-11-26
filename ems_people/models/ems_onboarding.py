from odoo import fields, models


class EmsOnboarding(models.Model):
    _name = 'ems.onboarding'
    _description = 'Onboarding Task'
    _order = 'employee_id, due_date, id'

    name = fields.Char('Task', required=True)
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade')
    owner_id = fields.Many2one('res.users', string='Owner')
    due_date = fields.Date()
    done = fields.Boolean()
    date_done = fields.Date(readonly=True)

    def write(self, vals):
        if 'done' in vals:
            vals['date_done'] = fields.Date.context_today(self) if vals['done'] else False
        return super().write(vals)


class HrEmployeeOnboarding(models.Model):
    _inherit = 'hr.employee'

    ems_onboarding_ids = fields.One2many('ems.onboarding', 'employee_id', string='Onboarding Tasks')
