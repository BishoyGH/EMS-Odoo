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
    hours_per_week = fields.Float('Hours / Week', compute='_compute_hours_per_week',
                                  inverse='_inverse_hours_per_week', store=True, readonly=False)
    engagement_pct = fields.Float('Engagement %', compute='_compute_engagement')

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

    @api.depends('date_from', 'date_to', 'hours_per_day', 'employee_id')
    def _compute_hours(self):
        for rec in self:
            days = rec.employee_id._ems_working_days(rec.date_from, rec.date_to) if rec.employee_id else 0
            rec.days = days
            rec.hours = days * rec.hours_per_day

    @api.depends('hours_per_day')
    def _compute_hours_per_week(self):
        for rec in self:
            rec.hours_per_week = rec.hours_per_day * 5.0

    def _inverse_hours_per_week(self):
        for rec in self:
            rec.hours_per_day = rec.hours_per_week / 5.0

    @api.depends('hours_per_day', 'employee_id.ems_hours_week')
    def _compute_engagement(self):
        for rec in self:
            capacity = (rec.employee_id.ems_hours_week or 40.0) / 5.0
            rec.engagement_pct = rec.hours_per_day / capacity * 100.0 if capacity else 0.0

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

    def _ems_count_days(self, date_from, date_to):
        """Working days between two dates for this employee: calendar, public holidays and approved leave."""
        self.ensure_one()
        return self.employee_id._ems_working_days(date_from, date_to)

    # ------------------------------------------------------------------ planner grid (drag and drop)
    @api.model
    def get_planner_data(self, date_from=False, weeks=8):
        """Employees x weeks grid for the OWL planner. Hours are working hours in each week,
        so leave and public holidays are already taken out."""
        today = fields.Date.context_today(self)
        anchor = fields.Date.to_date(date_from) if date_from else today
        start = anchor - timedelta(days=anchor.weekday())
        weeks = max(1, min(int(weeks or 8), 26))
        columns = [{'index': i, 'start': fields.Date.to_string(start + timedelta(weeks=i)),
                    'end': fields.Date.to_string(start + timedelta(weeks=i, days=6)),
                    'label': 'W%s' % (start + timedelta(weeks=i)).isocalendar()[1],
                    'is_current': (start + timedelta(weeks=i)) <= today <= (start + timedelta(weeks=i, days=6))}
                   for i in range(weeks)]
        end = start + timedelta(weeks=weeks, days=-1)
        employees = self.env['hr.employee'].search([('ems_plannable', '=', True)], order='name')
        allocs = self.search([('date_from', '<=', end), ('date_to', '>=', start), ('employee_id', 'in', employees.ids)])
        by_emp = {}
        for alloc in allocs:
            by_emp.setdefault(alloc.employee_id.id, []).append(alloc)
        rows = []
        for emp in employees:
            capacity = emp.ems_hours_week or 40.0
            cells = []
            for col in columns:
                w_start = fields.Date.to_date(col['start'])
                w_end = fields.Date.to_date(col['end'])
                chips, total = [], 0.0
                for alloc in by_emp.get(emp.id, []):
                    if alloc.date_from <= w_end and alloc.date_to >= w_start:
                        days = emp._ems_working_days(max(alloc.date_from, w_start), min(alloc.date_to, w_end))
                        hours = days * alloc.hours_per_day
                        total += hours
                        chips.append({
                            'id': alloc.id, 'name': alloc.name, 'project': alloc.project_id.display_name,
                            'code': alloc.project_id.ems_code or alloc.project_id.display_name[:8],
                            'hours': round(hours, 1), 'tentative': alloc.tentative,
                            'color': alloc.project_id.id % 12,
                            'from': fields.Date.to_string(alloc.date_from), 'to': fields.Date.to_string(alloc.date_to),
                        })
                cells.append({'index': col['index'], 'chips': chips, 'total': round(total, 1),
                              'pct': round(total / capacity * 100.0, 0) if capacity else 0.0})
            rows.append({'id': emp.id, 'name': emp.name, 'code': emp.ems_code or '', 'title': emp.job_title or '',
                         'capacity': capacity, 'cells': cells})
        return {'weeks': columns, 'rows': rows, 'start': fields.Date.to_string(start)}

    @api.model
    def move_allocation(self, alloc_id, employee_id, week_shift=0):
        """Drag and drop: give the allocation to another person and/or shift it by whole weeks."""
        alloc = self.browse(alloc_id)
        vals = {}
        if employee_id and employee_id != alloc.employee_id.id:
            vals['employee_id'] = employee_id
        if week_shift:
            delta = timedelta(weeks=int(week_shift))
            vals.update(date_from=alloc.date_from + delta, date_to=alloc.date_to + delta)
        if vals:
            alloc.write(vals)
        return True
