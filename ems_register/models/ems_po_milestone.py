from odoo import api, fields, models


class EmsPoMilestone(models.Model):
    _name = 'ems.po.milestone'
    _description = 'PO Payment Milestone'
    _order = 'sequence, id'

    order_id = fields.Many2one('purchase.order', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char('Milestone', required=True)
    percent = fields.Float('%')
    currency_id = fields.Many2one(related='order_id.currency_id')
    amount = fields.Monetary(compute='_compute_amount', store=True, readonly=False)
    due_on = fields.Char('Due On')

    @api.depends('percent', 'order_id.amount_untaxed')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.order_id.amount_untaxed * rec.percent / 100.0
