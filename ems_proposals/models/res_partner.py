from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ems_bid_count = fields.Integer('Bids', compute='_compute_ems_bids')
    ems_won_count = fields.Integer('Won', compute='_compute_ems_bids')
    ems_success_pct = fields.Float('Success %', compute='_compute_ems_bids')

    def _compute_ems_bids(self):
        Lead = self.env['crm.lead'].with_context(active_test=False)
        for partner in self:
            leads = Lead.search([('partner_id', '=', partner.id), ('type', '=', 'opportunity')])
            won = leads.filtered(lambda l: l.stage_id.is_won)
            partner.ems_bid_count = len(leads)
            partner.ems_won_count = len(won)
            partner.ems_success_pct = (len(won) / len(leads) * 100.0) if leads else 0.0
