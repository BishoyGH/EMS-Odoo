from odoo import fields, models


class EmsAddRevisionWizard(models.TransientModel):
    _name = 'ems.add.revision.wizard'
    _description = 'Add Proposal Revision'

    lead_id = fields.Many2one('crm.lead', required=True)
    revision = fields.Char(required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    amount = fields.Float(required=True)
    note = fields.Char()

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead = self.env['crm.lead'].browse(res.get('lead_id') or self.env.context.get('default_lead_id'))
        if lead and 'revision' in fields_list:
            res['revision'] = 'R%02d' % lead.ems_revision_count
        return res

    def action_confirm(self):
        self.ensure_one()
        self.env['ems.lead.revision'].create({
            'lead_id': self.lead_id.id, 'revision': self.revision, 'date': self.date,
            'amount': self.amount, 'note': self.note,
        })
        self.lead_id.message_post(body='Revision %s added: %s' % (self.revision, self.amount))
        return {'type': 'ir.actions.act_window_close'}
