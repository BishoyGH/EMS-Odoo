from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EmsAllocation(models.Model):
    _name = 'ems.allocation'
    _description = 'Resource Allocation'
    _inherit = ['mail.thread']
    _order = 'date_from desc, employee_id'

    name = fields.Char('Action / Task', required=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, tracking=True,
                                  domain=[('ems_plannable', '=', True)])
    project_id = fields.Many2one('project.project', required=True, index=True)
    service_id = fields.Many2one('ems.project.service', domain="[('project_id', '=', project_id)]")
    milestone_id = fields.Many2one('project.milestone', domain="[('project_id', '=', project_id)]")
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    hours_per_day = fields.Float(default=8.0, required=True)
    tentative = fields.Boolean()
    days = fields.Integer('Working Days', compute='_compute_hours', store=True)
    hours = fields.Float('Planned Hours', compute='_compute_hours', store=True)
    cost = fields.Float('Planned Cost', compute='_compute_cost', store=True,
                        groups='ems_base.group_ems_rates')
    week_start = fields.Date(compute='_compute_week_start', store=True)
    overbooked = fields.Boolean(compute='_compute_overbooked')

    @api.constrains('date_from', 'date_to', 'hours_per_day')
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_('The end date cannot be before the start date.'))
            if rec.hours_per_day < 0 or rec.hours_per_day > 24:
                raise ValidationError(_('Hours per day must be between 0 and 24.'))

    @api.depends('date_from')
    def _compute_week_start(self):
        for rec in self:
            rec.week_start = rec.date_from - timedelta(days=rec.date_from.weekday()) if rec.date_from else False

    @api.depends('date_from', 'date_to', 'hours_per_day')
    def _compute_hours(self):
        for rec in self:
            days = 0
            if rec.date_from and rec.date_to and rec.date_to >= rec.date_from:
                day = rec.date_from
                while day <= rec.date_to:
                    if day.weekday() < 5:  # Mon-Fri; public holidays are handled by the planner users
                        days += 1
                    day += timedelta(days=1)
            rec.days = days
            rec.hours = days * rec.hours_per_day

    @api.depends('hours', 'employee_id.ems_grade_id.cost_rate', 'employee_id.ems_cost_rate')
    def _compute_cost(self):
        for rec in self:
            rec.cost = rec.hours * (rec.employee_id._ems_cost_per_hour() if rec.employee_id else 0.0)

    def _compute_overbooked(self):
        for rec in self:
            if not (rec.employee_id and rec.date_from and rec.date_to and isinstance(rec.id, int)):
                rec.overbooked = False
                continue
            rec.overbooked = rec._ems_overlap_hours_per_day() > (rec.employee_id.ems_hours_week or 40.0) / 5.0 + 1e-6

    def _ems_overlap_hours_per_day(self):
        """Peak daily load for the employee over this allocation's period (non-tentative counts too)."""
        self.ensure_one()
        others = self.search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '<=', self.date_to), ('date_to', '>=', self.date_from)])
        return sum(others.mapped('hours_per_day'))

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id and not self.project_id:
            self.project_id = self.service_id.project_id
