from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmsPlanPersonWizard(models.TransientModel):
    """Plan a person on the selected milestone (exe: Services > Plan a person)."""
    _name = 'ems.plan.person.wizard'
    _description = 'Plan a Person on a Milestone'

    milestone_id = fields.Many2one('project.milestone', required=True)
    employee_id = fields.Many2one('hr.employee', required=True, domain=[('ems_plannable', '=', True)])
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    hours_per_day = fields.Float(default=4.0, required=True)
    tentative = fields.Boolean()
    name = fields.Char('Action / Task')
    capacity_note = fields.Char(compute='_compute_capacity_note')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ms = self.env['project.milestone'].browse(res.get('milestone_id') or self.env.context.get('default_milestone_id'))
        if ms:
            today = fields.Date.context_today(self)
            res.setdefault('date_from', ms.ems_date_start or today)
            res.setdefault('date_to', ms.deadline or ms.ems_date_start or today)
            res.setdefault('name', ms.name)
            if ms.ems_owner_id:
                emp = self.env['hr.employee'].search([('user_id', '=', ms.ems_owner_id.id)], limit=1)
                if emp:
                    res.setdefault('employee_id', emp.id)
        return res

    @api.depends('employee_id', 'date_from', 'date_to', 'hours_per_day')
    def _compute_capacity_note(self):
        for wiz in self:
            note = False
            if wiz.employee_id and wiz.date_from and wiz.date_to:
                booked = sum(self.env['ems.allocation'].search([
                    ('employee_id', '=', wiz.employee_id.id),
                    ('date_from', '<=', wiz.date_to), ('date_to', '>=', wiz.date_from)]).mapped('hours_per_day'))
                capacity = (wiz.employee_id.ems_hours_week or 40.0) / 5.0
                total = booked + wiz.hours_per_day
                note = _('Already booked %(b).1f h/day + %(n).1f h/day = %(p).0f%% of a %(c).1f h day.',
                         b=booked, n=wiz.hours_per_day, p=total / capacity * 100.0 if capacity else 0.0, c=capacity)
            wiz.capacity_note = note

    def action_confirm(self):
        self.ensure_one()
        ms = self.milestone_id
        alloc = self.env['ems.allocation'].create({
            'name': self.name or ms.name, 'employee_id': self.employee_id.id, 'project_id': ms.project_id.id,
            'service_id': ms.ems_service_id.id, 'milestone_id': ms.id,
            'date_from': self.date_from, 'date_to': self.date_to,
            'hours_per_day': self.hours_per_day, 'tentative': self.tentative,
        })
        return {'type': 'ir.actions.act_window', 'res_model': 'ems.allocation', 'res_id': alloc.id, 'view_mode': 'form'}
