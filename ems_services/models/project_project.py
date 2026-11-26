from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    ems_service_ids = fields.One2many('ems.project.service', 'project_id', string='Services')
    ems_service_count = fields.Integer(compute='_compute_ems_service_count')

    @api.depends('ems_service_ids')
    def _compute_ems_service_count(self):
        for project in self:
            project.ems_service_count = len(project.ems_service_ids)
