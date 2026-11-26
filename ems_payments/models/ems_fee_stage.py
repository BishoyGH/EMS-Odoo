from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmsFeeStage(models.Model):
    _name = 'ems.fee.stage'
    _description = 'Project Fee Stage'
    _inherit = ['mail.thread']
    _order = 'project_id, sequence, id'

    project_id = fields.Many2one('project.project', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    phase = fields.Char()
    name = fields.Char('Stage', required=True)
    trigger = fields.Char('Trigger Evidence')
    basis = fields.Selection([('percent', '% of contract'), ('fixed', 'Fixed amount')], default='percent', required=True)
    percent = fields.Float('%')
    currency_id = fields.Many2one(related='project_id.ems_currency_id', store=True)
    amount = fields.Monetary(compute='_compute_amount', store=True, readonly=False)
    progress = fields.Float('Progress %')
    eligible = fields.Boolean('Eligible to Invoice', tracking=True,
                              help='Tick when the trigger evidence has been received and approved.')
    invoice_ids = fields.One2many('account.move', 'ems_fee_stage_id', string='Invoices')
    invoiced_amount = fields.Monetary(compute='_compute_invoiced', store=False)
    state = fields.Selection([('todo', 'To Invoice'), ('invoiced', 'Invoiced')],
                             compute='_compute_invoiced', string='Status')

    @api.depends('basis', 'percent', 'project_id.ems_contract_value')
    def _compute_amount(self):
        for rec in self:
            if rec.basis == 'percent':
                rec.amount = rec.project_id.ems_contract_value * rec.percent / 100.0

    @api.depends('invoice_ids.state', 'invoice_ids.amount_untaxed')
    def _compute_invoiced(self):
        for rec in self:
            live = rec.invoice_ids.filtered(lambda m: m.state != 'cancel')
            rec.invoiced_amount = sum(live.mapped('amount_untaxed'))
            rec.state = 'invoiced' if live else 'todo'

    def action_invoice_stage(self):
        self.ensure_one()
        if not self.eligible:
            raise UserError(_('This stage is not marked eligible: trigger evidence is required before invoicing.'))
        if self.state == 'invoiced':
            raise UserError(_('This stage already has an invoice.'))
        project = self.project_id
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': project.partner_id.id,
            'ems_project_id': project.id,
            'ems_fee_stage_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'name': '%s - %s' % (project.display_name, self.name),
                'quantity': 1,
                'price_unit': self.amount,
            })],
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': invoice.id, 'view_mode': 'form',
        }
