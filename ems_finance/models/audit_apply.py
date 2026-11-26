from odoo import models


class ProjectProjectAudit(models.Model):
    _name = 'project.project'
    _inherit = ['project.project', 'ems.audit.mixin']
    _ems_audit_fields = {
        'ems_contract_value': 'price', 'ems_variation_value': 'price', 'ems_delivery_budget': 'baseline',
        'ems_sub_budget': 'baseline', 'ems_sale_order_id': 'baseline', 'ems_baseline_value': 'baseline',
        'ems_closed': 'closure', 'ems_mobilised': 'baseline', 'ems_code': 'baseline',
    }


class FeeStageAudit(models.Model):
    _name = 'ems.fee.stage'
    _inherit = ['ems.fee.stage', 'ems.audit.mixin']
    _ems_audit_fields = {
        'eligible': 'trigger', 'trigger': 'trigger', 'amount': 'price', 'percent': 'price', 'basis': 'price',
    }


class GradeAudit(models.Model):
    _name = 'ems.grade'
    _inherit = ['ems.grade', 'ems.audit.mixin']
    _ems_audit_fields = {'cost_rate': 'rate', 'charge_rate': 'rate'}


class EmployeeAudit(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'ems.audit.mixin']
    _ems_audit_fields = {'ems_cost_rate': 'rate', 'ems_grade_id': 'rate'}


class MilestoneAudit(models.Model):
    _name = 'project.milestone'
    _inherit = ['project.milestone', 'ems.audit.mixin']
    _ems_audit_fields = {'is_reached': 'closure', 'ems_state': 'closure', 'deadline': 'baseline'}


class TaskAudit(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'ems.audit.mixin']
    _ems_audit_fields = {'state': 'closure', 'allocated_hours': 'baseline'}


class PurchaseLineAudit(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'ems.audit.mixin']
    _ems_audit_fields = {'price_unit': 'price', 'product_qty': 'price'}


class PurchaseOrderAudit(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'ems.audit.mixin']
    _ems_audit_fields = {'ems_project_id': 'baseline', 'ems_overhead': 'baseline'}


class AnalyticLineAudit(models.Model):
    _name = 'account.analytic.line'
    _inherit = ['account.analytic.line', 'ems.audit.mixin']
    _ems_audit_fields = {'ems_state': 'approval', 'unit_amount': 'other'}


class SaleOrderAudit(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'ems.audit.mixin']
    _ems_audit_fields = {'ems_award_po_ref': 'baseline', 'ems_ntp_date': 'baseline'}


class SaleOrderLineAudit(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'ems.audit.mixin']
    _ems_audit_fields = {'price_unit': 'price', 'product_uom_qty': 'price', 'discount': 'price', 'ems_not_awarded': 'price'}
