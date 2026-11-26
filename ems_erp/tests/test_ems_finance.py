from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestEmsFinance(TransactionCase):
    """UAT scripts C, D, F, G, H, J, K, L from the functional specification."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({'name': 'Fin Client', 'customer_rank': 1})
        cls.vendor = cls.env['res.partner'].create({'name': 'Fin Vendor', 'supplier_rank': 1})
        cls.lead = cls.env['crm.lead'].create({
            'name': 'Fin Tower', 'type': 'opportunity', 'partner_id': cls.client.id})
        cls.env['ems.lead.revision'].create({'lead_id': cls.lead.id, 'revision': 'R00', 'amount': 245000})
        wiz = cls.env['ems.award.wizard'].with_context(default_lead_id=cls.lead.id).create({
            'po_ref': 'PO-9', 'ntp_date': '2025-09-09'})
        wiz.line_ids = [Command.clear(),
                        Command.create({'name': 'Review items 1-7', 'amount': 125000, 'awarded': True}),
                        Command.create({'name': 'VE + connections + PT', 'amount': 120000, 'awarded': False})]
        wiz.action_confirm()
        cls.order = cls.lead.ems_sale_order_ids
        cls.project = cls.lead.ems_project_id
        cls.grade = cls.env['ems.grade'].create({'code': 'FG', 'name': 'Fin grade', 'cost_rate': 100})
        cls.emp = cls.env['hr.employee'].create({'name': 'Fin Emp', 'ems_grade_id': cls.grade.id})

    # --- C / D: award baseline ------------------------------------------------
    def test_award_baseline_excludes_unawarded_items(self):
        project = self.project
        self.assertEqual(self.order.state, 'sale')
        self.assertEqual(self.order.amount_untaxed, 125000)
        self.assertEqual(self.order.ems_excluded_amount, 120000)
        self.assertEqual(project.ems_contract_value, 125000)
        self.assertEqual(project.ems_baseline_value, 125000)
        self.assertEqual(project.ems_excluded_amount, 120000)
        self.assertEqual(project.ems_sale_order_id, self.order)
        self.assertTrue(project.account_id, 'analytic account created')
        self.assertEqual(project.ems_proposal_id, self.lead)
        self.assertTrue(self.lead.stage_id.is_won)
        # P0-P7 and billing milestones 25/50/25
        self.assertEqual(project.ems_wbs_count, 8)
        self.assertEqual(sorted(project.ems_fee_stage_ids.mapped('amount')), [31250, 31250, 62500])
        project.action_ems_apply_wbs()
        self.assertEqual(project.ems_wbs_count, 8, 'WBS template is idempotent')

    # --- H: variation needs signed approval -------------------------------------
    def test_variation_requires_signed_approval(self):
        var = self.env['ems.variation'].create({
            'project_id': self.project.id, 'title': 'PBSD', 'amount': 40000, 'added_budget': 20000})
        with self.assertRaises(UserError):
            var.action_approve()
        self.assertEqual(self.project.ems_total_value, 125000)
        var.write({'signed_by': 'Client GM', 'signed_date': '2025-11-01', 'signed_file': 'dGVzdA=='})
        var.action_approve()
        self.assertEqual(self.project.ems_total_value, 165000)
        self.assertEqual(self.project.ems_delivery_budget, 20000)
        var.action_revoke()
        self.assertEqual(self.project.ems_total_value, 125000)

    # --- F / L: timesheet cost snapshot -------------------------------------------
    def _timesheet(self, hours=8.0, name='Review work'):
        task = self.project.task_ids.filtered(lambda t: t.ems_wbs_code == 'P2')
        return self.env['account.analytic.line'].create({
            'project_id': self.project.id, 'task_id': task.id, 'employee_id': self.emp.id,
            'name': name, 'unit_amount': hours, 'date': '2025-09-16'})

    def test_timesheet_validation_and_snapshot(self):
        with self.assertRaises(ValidationError):
            self._timesheet(hours=-1)
        with self.assertRaises(ValidationError):
            self._timesheet(name='/')
        line = self._timesheet(8)
        line.action_ems_submit()
        self.assertEqual(line.ems_state, 'submitted')
        line.action_ems_approve()
        self.assertEqual(line.ems_cost_rate, 100)
        self.assertEqual(line.ems_cost_amount, 800)
        self.assertEqual(line.amount, -800)
        # UAT L: later rate change must not touch history
        self.grade.cost_rate = 150
        self.assertEqual(line.ems_cost_amount, 800)
        with self.assertRaises(UserError):
            line.unit_amount = 4
        self.assertEqual(self.project.ems_actual_labour, 800)
        self.assertEqual(self.project.ems_hours_actual, 8)
        log = self.env['ems.audit.log'].search([('res_model', '=', 'ems.grade'), ('res_id', '=', self.grade.id)])
        self.assertEqual(log.mapped('new_value'), ['150.0'])
        self.assertEqual(log.area, 'rate')

    def test_no_self_approval(self):
        user = new_test_user(self.env, login='ems_pm', groups='ems_base.group_ems_manager,ems_base.group_ems_rates')
        self.emp.user_id = user
        line = self._timesheet(2)
        with self.assertRaises((AccessError, UserError)):
            line.with_user(user).action_ems_approve()

    # --- G / K: PO versus bill without double counting, overhead ---------------------
    def _po(self, price, **kw):
        prod = self.env.ref('ems_register.product_subconsultancy').product_variant_id
        return self.env['purchase.order'].create(dict({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {'name': 'Freelancer', 'product_qty': 1, 'price_unit': price, 'product_id': prod.id})],
        }, **kw))

    def test_po_needs_project_or_overhead(self):
        po = self._po(1800)
        with self.assertRaises(UserError):
            po.button_confirm()
        po.ems_overhead = True
        po.button_confirm()
        analytic = self.env.ref('ems_finance.analytic_overhead')
        self.assertEqual(po.order_line.analytic_distribution, {str(analytic.id): 100})
        self.assertFalse(po.ems_project_id)

    def test_commitment_not_double_counted_with_bill(self):
        po = self._po(8000, ems_project_id=self.project.id)
        po.button_confirm()
        self.assertEqual(self.project.ems_open_commitment, 8000)
        self.assertEqual(self.project.ems_vendor_billed, 0)
        po.action_create_invoice()
        bill = po.invoice_ids
        bill.invoice_date = fields.Date.today()
        bill.action_post()
        self.project.invalidate_recordset()
        self.assertEqual(self.project.ems_vendor_billed, 8000)
        self.assertEqual(self.project.ems_open_commitment, 0)
        self.assertEqual(po.ems_open_amount, 0)
        eco = self.project._ems_economics()[self.project.id]
        self.assertEqual(eco['eac'] - eco['etc_labour'], 8000, 'PO + bill counted once')

    # --- J / K: invoicing, aging and margin -----------------------------------------
    def test_invoice_aging_and_margin(self):
        stage = self.project.ems_fee_stage_ids.sorted('sequence')[0]
        stage.eligible = True
        stage.action_invoice_stage()
        invoice = stage.invoice_ids
        invoice.invoice_date = fields.Date.today()
        invoice.invoice_date_due = fields.Date.subtract(fields.Date.today(), days=45)
        invoice.action_post()
        aging = self.env['ems.ar.aging'].search([('move_id', '=', invoice.id)])
        self.assertEqual(aging.bucket, '31_60')
        self.assertEqual(aging.days_overdue, 45)
        line = self._timesheet(10)
        line.action_ems_approve()
        eco = self.project._ems_economics()[self.project.id]
        self.assertEqual(eco['invoiced'], 31250)
        self.assertEqual(eco['actual_labour'], 1000)
        self.assertEqual(eco['contracted'], 125000)
        self.assertEqual(eco['forecast_margin'], 125000 - eco['eac'])
        self.env['ir.config_parameter'].set_str('ems.overhead_pct', '10')
        eco = self.project._ems_economics()[self.project.id]
        self.assertEqual(eco['overhead'], 12500)
        self.assertEqual(eco['margin_after_overhead'], eco['forecast_margin'] - 12500)
        snap = self.env['ems.profit.snapshot']._take(self.project)
        self.assertEqual(snap.contracted, 125000)

    # --- approval matrix / closure ----------------------------------------------------
    def test_approval_matrix_group_and_closure(self):
        plain = new_test_user(self.env, login='ems_plain', groups='ems_base.group_ems_user')
        var = self.env['ems.variation'].create({
            'project_id': self.project.id, 'title': 'X', 'amount': 1000,
            'signed_by': 'c', 'signed_date': '2025-01-01', 'signed_file': 'dGVzdA=='})
        with self.assertRaises(AccessError):
            var.with_user(plain).action_approve()
        with self.assertRaises(UserError):
            self.project.action_ems_close()
        self.project.with_context(ems_force_close=True).action_ems_close()
        self.assertTrue(self.project.ems_closed)
