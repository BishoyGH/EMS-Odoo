from odoo import fields, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    ems_summary = fields.Text('Role Summary')
    ems_responsibilities = fields.Html('Responsibilities')
    ems_qualifications = fields.Html('Qualifications')
