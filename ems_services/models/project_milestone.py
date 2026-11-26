from odoo import fields, models


class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    ems_service_id = fields.Many2one('ems.project.service', string='Service', domain="[('project_id', '=', project_id)]")
    ems_date_start = fields.Date('Start')
    ems_budget_hours = fields.Float('Budget Hours')
    ems_owner_id = fields.Many2one('res.users', string='Owner')
    ems_state = fields.Selection([
        ('todo', 'To Do'), ('in_progress', 'In Progress'), ('review', 'Review'),
        ('done', 'Done'), ('blocked', 'Blocked'),
    ], string='EMS Status', default='todo')
    ems_progress = fields.Float('Progress %')
    ems_date_done = fields.Date('Done On', readonly=True)
    ems_description = fields.Html('Description')

    def action_ems_mark_done(self):
        self.write({
            'ems_state': 'done', 'ems_progress': 100.0, 'is_reached': True,
            'ems_date_done': fields.Date.context_today(self),
        })
