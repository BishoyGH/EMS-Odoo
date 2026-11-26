from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """The signed award. Lines flagged "not awarded" keep their proposal price for reference but carry zero quantity."""
    _inherit = 'sale.order'

    ems_lead_id = fields.Many2one('crm.lead', 'Proposal / Opportunity', copy=False, index=True)
    ems_award_po_ref = fields.Char('Client PO / Award Ref.')
    ems_award_po_date = fields.Date('PO / Award Date')
    ems_ntp_date = fields.Date('NTP Date')
    ems_project_id = fields.Many2one('project.project', 'EMS Project', copy=False, readonly=True)
    ems_excluded_amount = fields.Monetary('Not Awarded (excluded)', compute='_compute_ems_excluded',
                                          currency_field='currency_id')

    @api.depends('order_line.ems_excluded_price')
    def _compute_ems_excluded(self):
        for order in self:
            order.ems_excluded_amount = sum(order.order_line.mapped('ems_excluded_price'))

    def action_confirm(self):
        for order in self.filtered('ems_lead_id'):
            self.env['ems.approval.rule'].check('baseline', order, order.amount_untaxed)
        res = super().action_confirm()
        for order in self.filtered(lambda o: o.ems_lead_id and not o.ems_project_id):
            order._ems_build_project()
        return res

    def _ems_build_project(self):
        """Project from an approved award: analytic account, baseline, WBS P0-P7 and links."""
        self.ensure_one()
        lead = self.ems_lead_id
        project = lead.ems_project_id or self.ems_project_id
        values = {
            'ems_sale_order_id': self.id,
            'ems_contract_value': self.amount_untaxed,
            'ems_baseline_value': self.amount_untaxed,
            'ems_baseline_date': fields.Date.context_today(self),
            'ems_ntp_date': self.ems_ntp_date,
            'ems_client_po': self.ems_award_po_ref,
            'ems_proposal_id': lead.id,
        }
        if not project:
            project = self.env['project.project'].create(dict(values, **{
                'name': lead.name,
                'partner_id': self.partner_id.id,
                'ems_end_client_id': lead.ems_end_client_id.id,
                'ems_service': lead.ems_discipline,
                'allow_timesheets': True,
            }))
        else:
            project.write(values)
        project._ems_ensure_analytic_account()
        project.ems_baseline_hours = sum(project.ems_service_ids.mapped('budget_hours'))
        project.action_ems_apply_wbs()
        lead.write({'ems_project_id': project.id, 'ems_awarded_value': self.amount_untaxed})
        self.ems_project_id = project
        if not lead.stage_id.is_won:
            lead.action_set_won()
        return project


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    ems_not_awarded = fields.Boolean('Not Awarded', copy=False,
                                     help='Proposal item the client did not award. Never counted as revenue.')
    ems_excluded_price = fields.Monetary('Excluded Proposal Value', copy=False, currency_field='currency_id')
