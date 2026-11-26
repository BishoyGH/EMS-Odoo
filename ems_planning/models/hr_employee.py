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
