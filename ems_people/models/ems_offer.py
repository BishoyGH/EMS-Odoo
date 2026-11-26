from odoo import api, fields, models


class EmsOffer(models.Model):
    _name = 'ems.offer'
    _description = 'Offer Letter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'offer_date desc, id desc'

    name = fields.Char('Reference', default='New', copy=False, readonly=True)
    candidate = fields.Char(required=True, tracking=True)
    candidate_email = fields.Char('Candidate Email')
    job_id = fields.Many2one('hr.job', string='Role', tracking=True)
    grade_id = fields.Many2one('ems.grade', string='Grade')
    department_id = fields.Many2one('hr.department', string='Department')
    manager_id = fields.Many2one('hr.employee', string='Reports To')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    offer_date = fields.Date(default=fields.Date.context_today)
    valid_until = fields.Date('Valid Until')
    start_date = fields.Date('Proposed Start')
    salary_basic = fields.Monetary('Basic', groups='ems_base.group_ems_rates')
    salary_housing = fields.Monetary('Housing', groups='ems_base.group_ems_rates')
    salary_transport = fields.Monetary('Transport', groups='ems_base.group_ems_rates')
    salary_other = fields.Monetary('Other Allowances', groups='ems_base.group_ems_rates')
    salary_total = fields.Monetary('Total Monthly', compute='_compute_salary_total',
                                   groups='ems_base.group_ems_rates')
    probation_months = fields.Integer('Probation (months)', default=6)
    notice_days = fields.Integer('Notice (days)', default=30)
    leave_days = fields.Integer('Annual Leave (days)', default=30)
    air_ticket = fields.Char('Air Ticket')
    benefits = fields.Text('Other Benefits')
    non_compete = fields.Boolean('Non-compete')
    signatory_id = fields.Many2one('res.users', string='Signatory', default=lambda s: s.env.user)
    job_description = fields.Html('Job Description')
    letter_body = fields.Html('Letter Text')
    notes = fields.Text('Internal Notes')
    state = fields.Selection([
        ('draft', 'Draft'), ('sent', 'Sent'), ('accepted', 'Accepted'),
        ('declined', 'Declined'), ('withdrawn', 'Withdrawn'), ('expired', 'Expired'),
    ], default='draft', tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee Created', copy=False)

    @api.depends('salary_basic', 'salary_housing', 'salary_transport', 'salary_other')
    def _compute_salary_total(self):
        for rec in self:
            rec.salary_total = (rec.salary_basic + rec.salary_housing
                                + rec.salary_transport + rec.salary_other)

    @api.onchange('job_id')
    def _onchange_job_id(self):
        if self.job_id and not self.job_description:
            self.job_description = self.job_id.ems_responsibilities

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ems.offer') or 'New'
        return super().create(vals_list)

    def action_send(self):
        self.write({'state': 'sent'})

    def action_accept(self):
        self.write({'state': 'accepted'})

    def action_decline(self):
        self.write({'state': 'declined'})

    def action_withdraw(self):
        self.write({'state': 'withdrawn'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def action_create_employee(self):
        self.ensure_one()
        emp = self.env['hr.employee'].create({
            'name': self.candidate,
            'job_id': self.job_id.id,
            'department_id': self.department_id.id,
            'parent_id': self.manager_id.id,
            'work_email': self.candidate_email,
            'ems_grade_id': self.grade_id.id,
            'ems_date_start': self.start_date,
        })
        self.employee_id = emp
        return {
            'type': 'ir.actions.act_window', 'res_model': 'hr.employee',
            'res_id': emp.id, 'view_mode': 'form',
        }
