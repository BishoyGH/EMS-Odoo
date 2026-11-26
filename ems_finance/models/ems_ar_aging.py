from odoo import fields, models, tools


class EmsArAging(models.Model):
    """Accounts receivable aging per open client invoice, bucketed by days overdue."""
    _name = 'ems.ar.aging'
    _description = 'AR Aging'
    _auto = False
    _order = 'days_overdue desc'

    move_id = fields.Many2one('account.move', 'Invoice', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    project_id = fields.Many2one('project.project', 'Project', readonly=True)
    invoice_date = fields.Date(readonly=True)
    due_date = fields.Date(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    amount_total = fields.Monetary('Invoice Total', readonly=True)
    residual = fields.Monetary('Outstanding', readonly=True)
    days_overdue = fields.Integer('Days Overdue', readonly=True)
    bucket = fields.Selection([
        ('0_current', 'Not due'), ('1_30', '1-30 days'), ('31_60', '31-60 days'),
        ('61_90', '61-90 days'), ('90_plus', 'Over 90 days'),
    ], string='Aging Bucket', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT m.id AS id, m.id AS move_id, m.partner_id, m.ems_project_id AS project_id,
                       m.invoice_date, m.invoice_date_due AS due_date, m.currency_id,
                       (CASE WHEN m.move_type = 'out_refund' THEN -1 ELSE 1 END) * m.amount_total AS amount_total,
                       (CASE WHEN m.move_type = 'out_refund' THEN -1 ELSE 1 END) * m.amount_residual AS residual,
                       GREATEST(CURRENT_DATE - COALESCE(m.invoice_date_due, m.invoice_date), 0) AS days_overdue,
                       CASE
                         WHEN COALESCE(m.invoice_date_due, m.invoice_date) >= CURRENT_DATE THEN '0_current'
                         WHEN CURRENT_DATE - COALESCE(m.invoice_date_due, m.invoice_date) <= 30 THEN '1_30'
                         WHEN CURRENT_DATE - COALESCE(m.invoice_date_due, m.invoice_date) <= 60 THEN '31_60'
                         WHEN CURRENT_DATE - COALESCE(m.invoice_date_due, m.invoice_date) <= 90 THEN '61_90'
                         ELSE '90_plus' END AS bucket
                FROM account_move m
                WHERE m.state = 'posted' AND m.move_type IN ('out_invoice', 'out_refund')
                  AND m.amount_residual <> 0
            )""" % self._table)
