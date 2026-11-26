from datetime import timedelta

from odoo import api, models


class ReportWeeklyPlan(models.AbstractModel):
    _name = 'report.ems_planning.report_weekly_plan'
    _description = 'Weekly Plan Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['ems.weekly.plan.wizard'].browse(docids)
        start = wizard.week_start
        end = start + timedelta(days=6)
        allocations = self.env['ems.allocation'].search([
            ('date_from', '<=', end), ('date_to', '>=', start)], order='employee_id, project_id')
        by_employee = {}
        for alloc in allocations:
            by_employee.setdefault(alloc.employee_id, []).append(alloc)
        return {
            'doc_ids': docids, 'doc_model': 'ems.weekly.plan.wizard', 'docs': wizard,
            'start': start, 'end': end, 'by_employee': by_employee,
        }
