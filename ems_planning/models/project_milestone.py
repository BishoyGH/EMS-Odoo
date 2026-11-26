from odoo import _, fields, models


class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    ems_allocation_ids = fields.One2many('ems.allocation', 'milestone_id', string='Planned People')

    def action_ems_plan_person(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Plan a Person'), 'res_model': 'ems.plan.person.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_milestone_id': self.id},
        }
