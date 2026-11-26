from datetime import timedelta

from odoo import api, fields, models


class ReportEmsStatement(models.AbstractModel):
    _name = 'report.ems_payments.report_ems_statement'
    _description = 'EMS Customer Statement'

    @api.model
    def _get_report_values(self, docids, data=None):
        partners = self.env['res.partner'].browse(docids)
        today = fields.Date.context_today(self)
        statements = {}
        for partner in partners:
            moves = self.env['account.move'].search([
                ('partner_id', 'child_of', partner.commercial_partner_id.id),
                ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                '|', ('payment_state', 'in', ('not_paid', 'partial', 'in_payment')),
                ('invoice_date_due', '>=', today - timedelta(days=90)),
            ], order='ems_project_id, invoice_date')
            rows, buckets = [], [0.0] * 5
            for m in moves:
                late = max((today - m.invoice_date_due).days, 0) if m.invoice_date_due and m.amount_residual else 0
                rows.append({
                    'project': m.ems_project_id.display_name or '', 'name': m.name,
                    'date': m.invoice_date, 'due': m.invoice_date_due,
                    'amount': m.amount_total, 'received': m.amount_total - m.amount_residual,
                    'balance': m.amount_residual, 'late': late,
                })
                if m.amount_residual:
                    idx = 0 if late == 0 else 1 if late <= 30 else 2 if late <= 60 else 3 if late <= 90 else 4
                    buckets[idx] += m.amount_residual
            statements[partner.id] = {'rows': rows, 'buckets': buckets, 'total': sum(buckets)}
        return {'doc_ids': docids, 'doc_model': 'res.partner', 'docs': partners,
                'today': today, 'statements': statements}
