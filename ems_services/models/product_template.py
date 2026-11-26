from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ems_discipline = fields.Char('Discipline')
    ems_is_service_item = fields.Boolean('EMS Service Catalogue Item')
