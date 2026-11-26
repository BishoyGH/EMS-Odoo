from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ems_fee_stage_ids = fields.One2many('ems.fee.stage', 'project_id', string='Fee Stages')
    ems_invoice_ids = fields.One2many('account.move', 'ems_project_id', string='Client Invoices',
                                      domain=[('move_type', '=', 'out_invoice')])
    ems_invoiced = fields.Monetary('Invoiced (ex VAT)', currency_field='ems_currency_id', compute='_compute_ems_invoiced')
    ems_outstanding = fields.Monetary('Outstanding (incl. VAT)', currency_field='ems_currency_id', compute='_compute_ems_invoiced')
    ems_uninvoiced = fields.Monetary('Not Yet Invoiced', currency_field='ems_currency_id', compute='_compute_ems_invoiced')

    @api.depends('ems_invoice_ids.state', 'ems_invoice_ids.amount_untaxed', 'ems_invoice_ids.amount_residual',
                 'ems_total_value')
    def _compute_ems_invoiced(self):
        for project in self:
            posted = project.ems_invoice_ids.filtered(lambda m: m.state == 'posted')
            project.ems_invoiced = sum(posted.mapped('amount_untaxed'))
            project.ems_outstanding = sum(posted.mapped('amount_residual'))
            project.ems_uninvoiced = project.ems_total_value - project.ems_invoiced
