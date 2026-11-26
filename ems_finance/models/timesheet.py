from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

LOCKED = ('unit_amount', 'employee_id', 'date', 'task_id', 'project_id')


class AccountAnalyticLine(models.Model):
    """Timesheets: daily entry against WBS, weekly PM approval, cost rate snapshot at approval."""
    _inherit = 'account.analytic.line'

    ems_state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'),
    ], string='Approval', default='draft', copy=False, index=True)
    ems_wbs_code = fields.Char('WBS', related='task_id.ems_wbs_code', store=True)
    ems_cost_rate = fields.Float('Cost Rate Snapshot / h', copy=False, readonly=True,
                                 groups='ems_base.group_ems_rates')
    ems_cost_amount = fields.Float('Actual Cost', copy=False, readonly=True, groups='ems_base.group_ems_rates')
    ems_approved_by = fields.Many2one('res.users', 'Approved By', copy=False, readonly=True)
    ems_approved_on = fields.Datetime(copy=False, readonly=True)
    ems_out_of_scope = fields.Boolean('Outside Signed Scope',
                                      help='Work outside the award should become a proposed variation.')
    ems_week_start = fields.Date('Week', compute='_compute_ems_week', store=True)
    ems_overcapacity = fields.Boolean('Over Daily Capacity', compute='_compute_ems_overcapacity')

    @api.depends('date')
    def _compute_ems_week(self):
        for line in self:
            line.ems_week_start = line.date - timedelta(days=line.date.weekday()) if line.date else False

    def _compute_ems_overcapacity(self):
        for line in self:
            if not (line.project_id and line.employee_id and line.date):
                line.ems_overcapacity = False
                continue
            total = sum(self.sudo().search([
                ('employee_id', '=', line.employee_id.id), ('date', '=', line.date),
                ('project_id', '!=', False)]).mapped('unit_amount'))
            line.ems_overcapacity = total > (line.employee_id.sudo().ems_hours_week or 40.0) / 5.0 + 1e-6

    @api.constrains('unit_amount', 'name', 'project_id', 'employee_id', 'date')
    def _check_ems_timesheet(self):
        for line in self.filtered('project_id'):
            if line.unit_amount < 0:
                raise ValidationError(_('Negative hours are not allowed on a timesheet.'))
            if not line.name or line.name.strip() in ('', '/'):
                raise ValidationError(_('A description of the work is required on every timesheet entry.'))
            day_total = sum(self.sudo().search([
                ('employee_id', '=', line.employee_id.id), ('date', '=', line.date),
                ('project_id', '!=', False)]).mapped('unit_amount'))
            if day_total > 24:
                raise ValidationError(_('%(emp)s has more than 24 hours on %(date)s.',
                                        emp=line.employee_id.name, date=line.date))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('project_id') and not vals.get('name'):
                vals['name'] = '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('ems_timesheet_system') and any(f in vals for f in LOCKED):
            if self.filtered(lambda l: l.ems_state == 'approved'):
                raise UserError(_('Approved timesheets are locked. Ask a manager to reject the entry first.'))
        if vals.get('ems_state') in ('approved',) and not self.env.context.get('ems_timesheet_system'):
            raise UserError(_('Use the Approve button: it snapshots the cost rate.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda l: l.ems_state == 'approved'):
            raise UserError(_('Approved timesheets cannot be deleted.'))
        return super().unlink()

    def action_ems_submit(self):
        for line in self:
            if line.project_id and not line.task_id:
                raise UserError(_('Pick the WBS task before submitting.'))
        self.filtered(lambda l: l.ems_state in ('draft', 'rejected')).with_context(
            ems_timesheet_system=True).write({'ems_state': 'submitted'})

    def action_ems_approve(self):
        Rule = self.env['ems.approval.rule']
        for line in self.filtered(lambda l: l.ems_state in ('draft', 'submitted')):
            Rule.check('timesheet', line, line.unit_amount)
            if line.employee_id.user_id == self.env.user and self.env.uid != 1:
                raise UserError(_('You cannot approve your own timesheet.'))
            rate = line.employee_id.sudo()._ems_cost_per_hour() or line.employee_id.sudo().hourly_cost
            cost = line.unit_amount * rate
            line.sudo().with_context(ems_timesheet_system=True).write({
                'ems_state': 'approved', 'ems_cost_rate': rate, 'ems_cost_amount': cost,
                'ems_approved_by': self.env.user.id, 'ems_approved_on': fields.Datetime.now(),
                # keep the analytic ledger on the snapshot cost
                'amount': -cost,
            })
        return True

    def action_ems_reject(self):
        for line in self.filtered(lambda l: l.ems_state in ('submitted', 'approved')):
            line.sudo().with_context(ems_timesheet_system=True).write({
                'ems_state': 'rejected', 'ems_cost_rate': 0.0, 'ems_cost_amount': 0.0,
                'ems_approved_by': False, 'ems_approved_on': False})

    def action_ems_propose_variation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'ems.variation', 'view_mode': 'form',
            'context': {'default_project_id': self.project_id.id, 'default_title': self.name,
                        'default_reason': _('Out of scope work: %s (%.1f h on %s)') % (
                            self.name, self.unit_amount, self.date)},
        }
