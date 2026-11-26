from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    ems_wbs_code = fields.Char('WBS', index=True, help='P0-P7 delivery stage.')
    ems_gate = fields.Char('Gate / Deliverable')
