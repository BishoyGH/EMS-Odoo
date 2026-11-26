from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    ems_overhead = fields.Boolean(
        'Office Overhead', tracking=True,
        help='Tick for office purchases (for example a printer). They are never charged to a project.')
    ems_billed_amount = fields.Monetary('Billed (ex VAT)', currency_field='currency_id', compute='_compute_ems_billed')
    ems_open_amount = fields.Monetary('Open Commitment (ex VAT)', currency_field='currency_id',
                                      compute='_compute_ems_billed')

    @api.onchange('ems_overhead')
    def _onchange_ems_overhead(self):
        if self.ems_overhead:
            self.ems_project_id = False

    @api.constrains('ems_overhead', 'ems_project_id')
    def _check_ems_target(self):
        for po in self:
            if po.ems_overhead and po.ems_project_id:
                raise UserError(_('A purchase order is either an Office Overhead purchase or charged to a project, not both.'))

    @api.depends('order_line.invoice_lines.move_id.state', 'order_line.invoice_lines.price_subtotal', 'amount_untaxed')
    def _compute_ems_billed(self):
        for po in self:
            lines = po.order_line.invoice_lines.filtered(
                lambda l: l.move_id.state == 'posted' and l.display_type == 'product')
            billed = sum((-1.0 if l.move_id.move_type == 'in_refund' else 1.0) * l.price_subtotal for l in lines)
            po.ems_billed_amount = billed
            po.ems_open_amount = max(po.amount_untaxed - billed, 0.0) if po.state in ('purchase', 'done') else 0.0

    def button_confirm(self):
        for po in self:
            if not po.ems_project_id and not po.ems_overhead:
                raise UserError(_(
                    'Choose a project or tick "Office Overhead" before confirming the order. '
                    'Purchases are never attached to a project by default.'))
            self.env['ems.approval.rule'].check('po', po, po.amount_untaxed)
        res = super().button_confirm()
        self._ems_set_analytic()
        return res

    def _ems_set_analytic(self):
        overhead = self.env.ref('ems_finance.analytic_overhead', raise_if_not_found=False)
        for po in self:
            account = overhead if po.ems_overhead else po.ems_project_id.account_id
            if not account:
                continue
            for line in po.order_line.filtered(lambda l: not l.display_type and not l.analytic_distribution):
                line.analytic_distribution = {str(account.id): 100}
