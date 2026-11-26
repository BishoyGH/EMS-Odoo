from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ems_po_ids = fields.One2many('purchase.order', 'ems_project_id', string='Purchase Orders')
    ems_po_count = fields.Integer(compute='_compute_ems_committed')
    ems_committed = fields.Monetary('Committed POs', currency_field='ems_currency_id', compute='_compute_ems_committed')
    ems_sub_balance = fields.Monetary('Sub-budget Balance', currency_field='ems_currency_id', compute='_compute_ems_committed')

    @api.depends('ems_po_ids.state', 'ems_po_ids.amount_untaxed', 'ems_sub_budget')
    def _compute_ems_committed(self):
        for project in self:
            confirmed = project.ems_po_ids.filtered(lambda p: p.state in ('purchase', 'done'))
            project.ems_po_count = len(project.ems_po_ids)
            project.ems_committed = sum(confirmed.mapped('amount_untaxed'))
            project.ems_sub_balance = project.ems_sub_budget - project.ems_committed

    def action_view_ems_pos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Purchase Orders', 'res_model': 'purchase.order',
            'view_mode': 'list,form', 'domain': [('ems_project_id', '=', self.id)],
            'context': {'default_ems_project_id': self.id},
        }
