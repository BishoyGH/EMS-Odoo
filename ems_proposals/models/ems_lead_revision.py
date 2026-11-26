from odoo import api, fields, models


class EmsLeadRevision(models.Model):
    _name = 'ems.lead.revision'
    _description = 'Proposal Revision'
    _order = 'date desc, id desc'

    lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade', index=True)
    revision = fields.Char(required=True, default='R00')
    date = fields.Date(default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one('res.currency', related='lead_id.company_currency', store=True)
    amount = fields.Monetary(required=True)
    note = fields.Char()

    def _sync_lead(self):
        for lead in self.mapped('lead_id'):
            latest = lead.ems_revision_ids.sorted(lambda r: (r.date, r.id))[-1:]
            if latest:
                lead.expected_revenue = latest.amount

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_lead()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self._sync_lead()
        return res
