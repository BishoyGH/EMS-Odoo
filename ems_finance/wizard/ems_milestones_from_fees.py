from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmsMilestonesFromFees(models.TransientModel):
    """Create one project milestone per fee stage (exe: Services > Milestones from fee stages)."""
    _name = 'ems.milestones.from.fees'
    _description = 'Milestones from Fee Stages'

    project_id = fields.Many2one('project.project', required=True)
    stage_ids = fields.Many2many('ems.fee.stage', string='Fee Stages',
                                 domain="[('project_id', '=', project_id)]")
    service_id = fields.Many2one('ems.project.service', domain="[('project_id', '=', project_id)]")
    skip_existing = fields.Boolean('Skip stages that already have a milestone', default=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        project = self.env['project.project'].browse(res.get('project_id') or self.env.context.get('default_project_id'))
        if project:
            res['stage_ids'] = [(6, 0, project.ems_fee_stage_ids.ids)]
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.stage_ids:
            raise UserError(_('Select at least one fee stage.'))
        Milestone = self.env['project.milestone']
        created = Milestone
        for stage in self.stage_ids.sorted('sequence'):
            name = stage.name
            if self.skip_existing and Milestone.search_count([('project_id', '=', self.project_id.id), ('name', '=', name)]):
                continue
            created |= Milestone.create({
                'name': name, 'project_id': self.project_id.id, 'ems_service_id': self.service_id.id,
                'ems_description': _('<p>Billing trigger: %s (%s%%)</p>') % (stage.trigger or '-', stage.percent),
            })
        return {
            'type': 'ir.actions.act_window', 'name': _('Milestones'), 'res_model': 'project.milestone',
            'view_mode': 'list,form', 'domain': [('id', 'in', created.ids)] if created else [('project_id', '=', self.project_id.id)],
        }
