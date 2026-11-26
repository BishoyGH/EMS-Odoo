from odoo import fields, models


class EmsDataIssue(models.Model):
    """Data-quality finding raised while migrating or importing (spec: Data Issues sheet)."""
    _name = 'ems.data.issue'
    _description = 'EMS Data Issue'
    _inherit = ['mail.thread']
    _order = 'severity, id'

    name = fields.Char('Issue', required=True)
    code = fields.Char(index=True)
    severity = fields.Selection([
        ('1_critical', 'Critical'), ('2_high', 'High'), ('3_medium', 'Medium'), ('4_low', 'Low'),
    ], default='3_medium', required=True)
    source = fields.Char('Original Source')
    resolution = fields.Char('Required Resolution')
    res_model = fields.Char()
    res_id = fields.Integer()
    record_name = fields.Char('Record')
    run_id = fields.Many2one('ems.migration.run', ondelete='cascade')
    state = fields.Selection([('open', 'Open'), ('resolved', 'Resolved'), ('accepted', 'Accepted as is')],
                             default='open', tracking=True)
    owner_id = fields.Many2one('res.users', 'Owner')

    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_accept(self):
        self.write({'state': 'accepted'})

    def action_open_record(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id,
                'view_mode': 'form'}
