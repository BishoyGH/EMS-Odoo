from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ems_allocation_ids = fields.One2many('ems.allocation', 'employee_id')
    ems_booked_pct = fields.Float('Booked % (today)', compute='_compute_ems_booked_pct')

    @api.depends('ems_allocation_ids.date_from', 'ems_allocation_ids.date_to',
                 'ems_allocation_ids.hours_per_day', 'ems_hours_week')
    def _compute_ems_booked_pct(self):
        today = fields.Date.context_today(self)
        for emp in self:
            daily = sum(a.hours_per_day for a in emp.ems_allocation_ids
                        if a.date_from <= today <= a.date_to)
            capacity = (emp.ems_hours_week or 40.0) / 5.0
            emp.ems_booked_pct = daily / capacity * 100.0 if capacity else 0.0

    def _ems_working_days(self, date_from, date_to):
        """Working days in [date_from, date_to]: employee calendar minus public holidays and time off.
        Falls back to Monday-Friday when the employee has no working schedule."""
        self.ensure_one()
        if not date_from or not date_to or date_to < date_from:
            return 0
        employee = self.sudo()
        calendar = employee.resource_calendar_id
        if not calendar or not employee.resource_id:
            return sum(1 for i in range((date_to - date_from).days + 1)
                       if (date_from + timedelta(days=i)).weekday() < 5)
        tz = ZoneInfo(employee.tz or calendar.tz or 'UTC')
        start = datetime.combine(date_from, time.min, tzinfo=tz)
        end = datetime.combine(date_to, time.max, tzinfo=tz)
        intervals = calendar._work_intervals_batch(
            start, end, resources_per_tz={tz: employee.resource_id})[employee.resource_id.id]
        return len({interval[0].astimezone(tz).date() for interval in intervals})
