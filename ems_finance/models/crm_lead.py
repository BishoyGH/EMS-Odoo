from odoo import fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    ems_rfp_date = fields.Date('RFP Received')
    ems_bid_decision = fields.Selection([
        ('pending', 'Pending'), ('bid', 'Approved to Quote'), ('no_bid', 'No Bid'),
    ], string='Bid Decision', default='pending', tracking=True, copy=False)
    ems_bid_notes = fields.Text('Bid Evaluation',
                                help='Capacity, conflict of interest, expected hours, margin and risk.')
    ems_bid_approved_by = fields.Many2one('res.users', 'Bid Approved By', readonly=True, copy=False)
    ems_bid_date = fields.Date(readonly=True, copy=False)
    ems_sale_order_ids = fields.One2many('sale.order', 'ems_lead_id', string='Awards')
    ems_award_count = fields.Integer(compute='_compute_ems_award_count')

    def _compute_ems_award_count(self):
        for lead in self:
            lead.ems_award_count = len(lead.ems_sale_order_ids)

    def _ems_bid_decide(self, decision):
        for lead in self:
            self.env['ems.approval.rule'].check('bid', lead, lead.expected_revenue)
            lead.write({
                'ems_bid_decision': decision, 'ems_bid_approved_by': self.env.user.id,
                'ems_bid_date': fields.Date.context_today(lead),
            })

    def action_ems_bid(self):
        self._ems_bid_decide('bid')

    def action_ems_no_bid(self):
        self._ems_bid_decide('no_bid')

    def action_ems_award(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Award from Signed PO'), 'res_model': 'ems.award.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_lead_id': self.id},
        }

    def action_view_ems_awards(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Awards'), 'res_model': 'sale.order',
                'view_mode': 'list,form', 'domain': [('ems_lead_id', '=', self.id)]}
