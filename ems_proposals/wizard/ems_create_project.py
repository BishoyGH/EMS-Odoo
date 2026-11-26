from odoo import fields, models


class EmsCreateProjectWizard(models.TransientModel):
    _name = 'ems.create.project.wizard'
    _description = 'Create Register Project from Proposal'

    lead_id = fields.Many2one('crm.lead', required=True)
    name = fields.Char('Project Name', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer')
    contract_value = fields.Float('Contract Value')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead = self.env['crm.lead'].browse(res.get('lead_id') or self.env.context.get('default_lead_id'))
        if lead:
            res.update(name=lead.name, partner_id=lead.partner_id.id,
                       contract_value=lead.ems_awarded_value or lead.ems_last_fee)
        return res

    def action_confirm(self):
        self.ensure_one()
        project = self.env['project.project'].create({
            'name': self.name,
            'partner_id': self.partner_id.id,
            'ems_contract_value': self.contract_value,
            'ems_proposal_id': self.lead_id.id,
            'ems_end_client_id': self.lead_id.ems_end_client_id.id,
            'ems_service': self.lead_id.ems_discipline,
        })
        self.lead_id.ems_project_id = project
        return self.lead_id.action_open_project()
