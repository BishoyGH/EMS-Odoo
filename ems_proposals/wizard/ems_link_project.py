from odoo import fields, models, _
from odoo.exceptions import UserError


class EmsLinkProjectWizard(models.TransientModel):
    _name = 'ems.link.project.wizard'
    _description = 'Link Existing Project to Proposal'

    lead_id = fields.Many2one('crm.lead', required=True)
    project_id = fields.Many2one('project.project', string='Project', required=True,
                                 domain="[('ems_proposal_id', '=', False)]")

    def action_confirm(self):
        self.ensure_one()
        if self.lead_id.ems_project_id:
            raise UserError(_('This proposal is already linked to a project.'))
        self.project_id.ems_proposal_id = self.lead_id
        self.lead_id.ems_project_id = self.project_id
        return self.lead_id.action_open_project()
