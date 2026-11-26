from datetime import timedelta

from odoo import fields, models


class EmsWeeklyPlanWizard(models.TransientModel):
    _name = 'ems.weekly.plan.wizard'
    _description = 'Weekly Plan'

    week_start = fields.Date(
        'Week Starting', required=True,
        default=lambda s: fields.Date.context_today(s) - timedelta(days=fields.Date.context_today(s).weekday()))

    def action_print(self):
        self.ensure_one()
        return self.env.ref('ems_planning.action_report_weekly_plan').report_action(self)
