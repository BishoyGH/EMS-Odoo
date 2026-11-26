from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ems_code = fields.Char('EMS Project Code', copy=False, index=True, tracking=True,
                           help='yy-nnnn, generated automatically when empty.')
    ems_currency_id = fields.Many2one(
        'res.currency', string='EMS Currency',
        default=lambda self: self.env.company.currency_id)
    ems_contract_value = fields.Monetary('Contract Value', currency_field='ems_currency_id', tracking=True)
    ems_delivery_budget = fields.Monetary('Delivery Budget', currency_field='ems_currency_id')
    ems_sub_budget = fields.Monetary('Sub-consultant Budget', currency_field='ems_currency_id')
    ems_variation_value = fields.Monetary('Variations', currency_field='ems_currency_id')
    ems_total_value = fields.Monetary('Total Value', currency_field='ems_currency_id',
                                      compute='_compute_ems_total_value', store=True)
    ems_contract_ref = fields.Char('Contract Ref.')
    ems_client_po = fields.Char('Client PO')
    ems_service = fields.Char('Service')
    ems_account_manager_id = fields.Many2one('res.users', string='Account Manager')
    ems_authority = fields.Char('Authority')
    ems_authority_ref = fields.Char('Authority Ref.')
    ems_end_client_id = fields.Many2one('res.partner', string='End Client')
    ems_consultant_id = fields.Many2one('res.partner', string='Consultant')

    _ems_code_uniq = models.Constraint('unique(ems_code)', 'The EMS project code must be unique.')

    @api.depends('ems_contract_value', 'ems_variation_value')
    def _compute_ems_total_value(self):
        for rec in self:
            rec.ems_total_value = rec.ems_contract_value + rec.ems_variation_value

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ems_code'):
                vals['ems_code'] = self.env['ir.sequence'].next_by_code('ems.project.code')
        return super().create(vals_list)
