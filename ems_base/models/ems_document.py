from odoo import fields, models

DOCUMENT_CATEGORIES = [
    ('contract', 'Contract / PO / LOA'),
    ('proposal', 'Proposal'),
    ('rfp', 'RFP / Tender'),
    ('licence', 'Trade licence'),
    ('insurance', 'Insurance certificate'),
    ('bank', 'Bank letter'),
    ('drawing', 'Drawings / Models'),
    ('report', 'Report / Certificate'),
    ('correspondence', 'Correspondence'),
    ('invoice', 'Invoice / Receipt'),
    ('generated', 'Generated document'),
    ('other', 'Other'),
]


class EmsDocument(models.Model):
    """Categorised document attached to any record (the exe's Documents tabs)."""
    _name = 'ems.document'
    _description = 'EMS Document'
    _order = 'category, id desc'

    name = fields.Char('Title', required=True)
    category = fields.Selection(DOCUMENT_CATEGORIES, required=True, default='other', index=True)
    file = fields.Binary('File', attachment=True)
    filename = fields.Char('File Name')
    note = fields.Char('Note')
    date = fields.Date(default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', 'Added By', default=lambda self: self.env.user)
    res_model = fields.Char('Related Model', index=True)
    res_id = fields.Many2oneReference('Related Record', model_field='res_model', index=True)
