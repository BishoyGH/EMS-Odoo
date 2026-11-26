import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from odoo.addons.ems_base.tools.docx_builder import build_docx


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    ems_number = fields.Char('Proposal No.', copy=False, index=True, tracking=True)
    ems_category = fields.Selection([
        ('3p', '3rd Party Review'), ('design', 'Design'), ('supervision', 'Supervision'),
        ('other', 'Other'),
    ], string='Category', default='3p')
    ems_project_code = fields.Char('Project Code')
    ems_client_code = fields.Char('Client Code')
    ems_discipline = fields.Char('Discipline')
    ems_location = fields.Char('Location')
    ems_plot = fields.Char('Plot No.')
    ems_end_client_id = fields.Many2one('res.partner', string='End Client')
    ems_scope = fields.Text('Scope')
    ems_revision_ids = fields.One2many('ems.lead.revision', 'lead_id', string='Revisions')
    ems_revision_count = fields.Integer(compute='_compute_ems_revision', store=True)
    ems_first_fee = fields.Monetary(compute='_compute_ems_revision', store=True, string='First Fee', currency_field='company_currency')
    ems_last_fee = fields.Monetary(compute='_compute_ems_revision', store=True, string='Latest Fee', currency_field='company_currency')
    ems_last_revision = fields.Char(compute='_compute_ems_revision', store=True, string='Latest Revision')
    ems_date_submitted = fields.Date(compute='_compute_ems_revision', store=True, string='Submitted')
    ems_awarded_value = fields.Monetary('Awarded Value (ex VAT)', currency_field='company_currency')
    ems_competitor = fields.Char('Competitor')
    ems_competitor_fee = fields.Monetary('Competitor Fee', currency_field='company_currency')
    ems_follow_up_date = fields.Date('Last Follow-up')
    ems_follow_up_method = fields.Selection([('email', 'Email'), ('call', 'Call'), ('meeting', 'Meeting'), ('whatsapp', 'WhatsApp')])
    ems_client_response = fields.Text('Client Response')
    ems_next_follow_up = fields.Date('Next Follow-up', tracking=True)
    ems_next_follow_up_method = fields.Selection([('email', 'Email'), ('call', 'Call'), ('meeting', 'Meeting'), ('whatsapp', 'WhatsApp')])
    ems_folder = fields.Char('Document Folder')
    ems_proposal_file = fields.Char('Proposal File')
    ems_register_code = fields.Char('Legacy Register Code')
    ems_project_id = fields.Many2one('project.project', string='Register Project', copy=False)
    ems_overdue = fields.Boolean(compute='_compute_ems_overdue', search='_search_ems_overdue')

    @api.depends('ems_revision_ids.amount', 'ems_revision_ids.date', 'ems_revision_ids.revision')
    def _compute_ems_revision(self):
        for lead in self:
            revs = lead.ems_revision_ids.sorted(lambda r: (r.date or fields.Date.today(), r.id))
            lead.ems_revision_count = len(revs)
            lead.ems_first_fee = revs[:1].amount if revs else 0.0
            lead.ems_last_fee = revs[-1:].amount if revs else 0.0
            lead.ems_last_revision = revs[-1:].revision if revs else False
            lead.ems_date_submitted = revs[:1].date if revs else False

    def _compute_ems_overdue(self):
        today = fields.Date.context_today(self)
        for lead in self:
            lead.ems_overdue = bool(lead.ems_next_follow_up and lead.ems_next_follow_up < today
                                    and lead.active and not lead.stage_id.is_won)

    def _search_ems_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        if positive:
            return [('ems_next_follow_up', '<', today), ('stage_id.is_won', '=', False)]
        return ['|', ('ems_next_follow_up', '=', False), ('ems_next_follow_up', '>=', today)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ems_number') and vals.get('type', 'opportunity') == 'opportunity':
                vals['ems_number'] = self.env['ir.sequence'].next_by_code('ems.proposal')
        return super().create(vals_list)

    def action_add_revision(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Add Revision'),
            'res_model': 'ems.add.revision.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    def action_create_project(self):
        self.ensure_one()
        if self.ems_project_id:
            raise UserError(_('This proposal is already linked to a project.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Create Project'),
            'res_model': 'ems.create.project.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    def action_open_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'project.project',
            'res_id': self.ems_project_id.id, 'view_mode': 'form',
        }

    def action_link_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Link Existing Project'),
            'res_model': 'ems.link.project.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    def action_ems_proposal_docx(self):
        """Generate the proposal cover document (.docx) and file it in the Documents tab."""
        self.ensure_one()
        revisions = self.ems_revision_ids.sorted(lambda r: (r.date, r.id))
        blocks = [
            ('title', _('Proposal %s') % (self.ems_number or '')),
            ('h1', self.name),
            ('table', [
                [_('Client'), self.partner_id.name or ''],
                [_('End client'), self.ems_end_client_id.name or ''],
                [_('Location / plot'), ' / '.join(filter(None, [self.ems_location, self.ems_plot]))],
                [_('Discipline'), self.ems_discipline or ''],
                [_('Latest revision'), self.ems_last_revision or ''],
                [_('Fee (ex VAT)'), '%.2f' % self.ems_last_fee],
            ]),
            ('h2', _('Scope of services')),
            ('p', self.ems_scope or html2plaintext(self.description or '')),
            ('h2', _('Fee revisions')),
            ('table', [[_('Revision'), _('Date'), _('Amount (ex VAT)'), _('Note')]]
                      + [[r.revision, str(r.date), '%.2f' % r.amount, r.note or ''] for r in revisions]),
            ('p', _('Fees exclude VAT. Optional services are quoted separately and are not part of the award until accepted.')),
        ]
        filename = 'Proposal %s.docx' % (self.ems_number or self.id)
        doc = self.env['ems.document'].create({
            'name': filename, 'category': 'proposal', 'filename': filename,
            'file': base64.b64encode(build_docx(blocks)).decode(),
            'res_model': self._name, 'res_id': self.id,
        })
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/ems.document/%s/file/%s?download=true' % (doc.id, filename)}

    def action_unlink_project(self):
        self.write({'ems_project_id': False})


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ems_proposal_id = fields.Many2one('crm.lead', string='Proposal', copy=False)


class CrmLeadDocs(models.Model):
    _inherit = 'crm.lead'

    ems_document_ids = fields.One2many(
        'ems.document', 'res_id', string='Documents', domain=[('res_model', '=', 'crm.lead')])
