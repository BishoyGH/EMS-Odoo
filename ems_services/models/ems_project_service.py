from odoo import api, fields, models


class EmsProjectService(models.Model):
    _name = 'ems.project.service'
    _description = 'Project Service / Cost Code'
    _inherit = ['mail.thread']
    _order = 'project_id, code'

    project_id = fields.Many2one('project.project', required=True, ondelete='cascade', index=True)
    code = fields.Char('Sub-code', required=True)
    cost_code = fields.Char(compute='_compute_cost_code', store=True, index=True)
    name = fields.Char(required=True)
    discipline = fields.Char()
    product_id = fields.Many2one('product.product', string='Catalogue Item')
    currency_id = fields.Many2one(related='project_id.ems_currency_id', store=True)
    fee = fields.Monetary()
    budget_hours = fields.Float()
    manager_id = fields.Many2one('res.users', string='Manager')
    state = fields.Selection([
        ('planned', 'Planned'), ('active', 'Active'), ('on_hold', 'On Hold'),
        ('done', 'Done'), ('cancelled', 'Cancelled'),
    ], default='planned', tracking=True)
    date_start = fields.Date()
    date_end = fields.Date()
    notes = fields.Text()
    milestone_ids = fields.One2many('project.milestone', 'ems_service_id')
    milestone_count = fields.Integer(compute='_compute_milestone_count')

    _cost_code_uniq = models.Constraint('unique(project_id, code)', 'Sub-code must be unique per project.')

    @api.depends('project_id.ems_code', 'code')
    def _compute_cost_code(self):
        for rec in self:
            rec.cost_code = '%s-%s' % (rec.project_id.ems_code or '', rec.code or '')

    @api.depends('milestone_ids')
    def _compute_milestone_count(self):
        for rec in self:
            rec.milestone_count = len(rec.milestone_ids)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.name or self.product_id.name
            self.fee = self.fee or self.product_id.list_price
            self.discipline = self.discipline or self.product_id.ems_discipline

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s' % (rec.cost_code or '', rec.name or '')
