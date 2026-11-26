from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmsVariation(models.Model):
    """Variation register. Revenue and budget grow only after signed client approval."""
    _name = 'ems.variation'
    _description = 'Project Variation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char('Number', default='New', copy=False, readonly=True)
    title = fields.Char(required=True, tracking=True)
    project_id = fields.Many2one('project.project', required=True, tracking=True, index=True)
    currency_id = fields.Many2one(related='project_id.ems_currency_id', store=True)
    reason = fields.Text('Scope / Reason')
    quotation_ref = fields.Char('Quotation Ref.')
    amount = fields.Monetary('Added Revenue (ex VAT)', tracking=True)
    added_budget = fields.Monetary('Added Delivery Budget')
    added_days = fields.Integer('Added Days')
    technical_owner_id = fields.Many2one('res.users', 'Technical Owner')
    crs_ref = fields.Char('CRS Comment Ref.')
    state = fields.Selection([
        ('draft', 'Proposed'), ('submitted', 'Submitted to Client'),
        ('approved', 'Approved (signed)'), ('rejected', 'Rejected'), ('cancel', 'Cancelled'),
    ], default='draft', tracking=True, copy=False)
    signed_by = fields.Char('Client Signatory', tracking=True)
    signed_date = fields.Date('Signed On', tracking=True)
    signed_file = fields.Binary('Signed Approval', attachment=True)
    signed_filename = fields.Char()
    approved_by_id = fields.Many2one('res.users', 'Approved By', readonly=True, copy=False)
    approved_on = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ems.variation') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        self.filtered(lambda v: v.state == 'draft').write({'state': 'submitted'})

    def action_approve(self):
        for var in self:
            if var.state not in ('draft', 'submitted'):
                raise UserError(_('Only proposed or submitted variations can be approved.'))
            if not (var.signed_file and var.signed_by and var.signed_date):
                raise UserError(_(
                    'A variation needs signed client approval (signatory, date and the signed document) '
                    'before revenue or budget can increase.'))
            self.env['ems.approval.rule'].check('variation', var, var.amount)
            project = var.project_id
            project.write({
                'ems_variation_value': project.ems_variation_value + var.amount,
                'ems_delivery_budget': project.ems_delivery_budget + var.added_budget,
            })
            var.write({'state': 'approved', 'approved_by_id': self.env.user.id, 'approved_on': fields.Datetime.now()})

    def action_reject(self):
        self.filtered(lambda v: v.state in ('draft', 'submitted')).write({'state': 'rejected'})

    def action_revoke(self):
        """Take an approved variation back out of the project values (kept in history)."""
        for var in self.filtered(lambda v: v.state == 'approved'):
            project = var.project_id
            project.write({
                'ems_variation_value': project.ems_variation_value - var.amount,
                'ems_delivery_budget': project.ems_delivery_budget - var.added_budget,
            })
            var.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda v: v.state in ('rejected', 'cancel')).write({'state': 'draft'})
