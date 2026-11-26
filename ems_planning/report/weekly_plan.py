from datetime import timedelta

from odoo import api, fields, models


class ReportWeeklyPlan(models.AbstractModel):
    _name = 'report.ems_planning.report_weekly_plan'
    _description = 'Weekly Plan Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['ems.weekly.plan.wizard'].browse(docids)
        start = wizard.week_start
        end = start + timedelta(days=6)
        days = [start + timedelta(days=i) for i in range(5)]
        Allocation = self.env['ems.allocation']
        allocations = Allocation.search([
            ('date_from', '<=', end), ('date_to', '>=', start)], order='employee_id, project_id, date_from')
        next_allocs = Allocation.search([
            ('date_from', '<=', end + timedelta(days=7)), ('date_to', '>', end)], order='project_id')
        by_employee = {}
        for alloc in allocations:
            by_employee.setdefault(alloc.employee_id, []).append(alloc)
        plans = []
        for employee, allocs in by_employee.items():
            rows, total = [], 0.0
            for a in allocs:
                cells = [a.hours_per_day if a.date_from <= d <= a.date_to else 0.0 for d in days]
                total += sum(cells)
                rows.append({'alloc': a, 'cells': cells, 'hours': sum(cells)})
            leave = self.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id), ('state', '=', 'validate'),
                ('request_date_from', '<=', end), ('request_date_to', '>=', start)])
            nxt = next_allocs.filtered(lambda a: a.employee_id == employee)
            milestones = allocs and self.env['project.milestone'].search([
                ('id', 'in', [a.milestone_id.id for a in allocs if a.milestone_id]),
                ('deadline', '>=', start), ('deadline', '<=', end)])
            plans.append({
                'employee': employee, 'rows': rows, 'total': total,
                'capacity': 40.0, 'leave': ', '.join(leave.mapped('display_name')),
                'milestones': ', '.join(milestones.mapped('name')) if milestones else '',
                'next': ', '.join('%s %s' % (a.project_id.ems_code or a.project_id.display_name, a.name) for a in nxt),
            })
        return {
            'doc_ids': docids, 'doc_model': 'ems.weekly.plan.wizard', 'docs': wizard,
            'start': start, 'end': end, 'days': days, 'plans': plans,
            'week_no': start.isocalendar()[1], 'next_week_no': (end + timedelta(days=1)).isocalendar()[1],
            'now': fields.Datetime.now(),
        }
