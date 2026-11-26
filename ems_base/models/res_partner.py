from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ems_category = fields.Selection([
        ('company', 'Company'),
        ('freelancer', 'Licensed freelancer'),
        ('individual', 'Individual consultant'),
    ], string='EMS Category')
    ems_is_end_client = fields.Boolean('End Client')
    ems_is_consultant = fields.Boolean('Consultant')
    ems_sector = fields.Char('Sector')
    ems_licence_no = fields.Char('Trade Licence No.')
    ems_licence_expiry = fields.Date('Licence Expiry')
    ems_client_payment_days = fields.Integer('Client Payment Days', default=30)
    ems_profile = fields.Text('Profile / Notes')

    ems_document_ids = fields.One2many(
        'ems.document', 'res_id', string='Documents', domain=[('res_model', '=', 'res.partner')])
