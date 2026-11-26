from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmsFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({'name': 'Test Client', 'customer_rank': 1})
        cls.vendor = cls.env['res.partner'].create({'name': 'Test Vendor', 'supplier_rank': 1})
        cls.project = cls.env['project.project'].create({
            'name': 'Test Project', 'partner_id': cls.client.id,
            'ems_contract_value': 100000, 'ems_sub_budget': 10000,
        })

    def test_project_code_and_total(self):
        self.assertTrue(self.project.ems_code)
        self.project.ems_variation_value = 5000
        self.assertEqual(self.project.ems_total_value, 105000)

    def test_proposal_revisions_and_project(self):
        lead = self.env['crm.lead'].create({'name': 'Bid', 'type': 'opportunity', 'partner_id': self.client.id})
        self.assertTrue(lead.ems_number)
        self.env['ems.lead.revision'].create({'lead_id': lead.id, 'revision': 'R00', 'amount': 245000})
        self.env['ems.lead.revision'].create({'lead_id': lead.id, 'revision': 'R01', 'amount': 125000,
                                              'date': '2099-01-01'})
        self.assertEqual(lead.ems_first_fee, 245000)
        self.assertEqual(lead.ems_last_fee, 125000)
        self.assertEqual(lead.expected_revenue, 125000)
        wiz = self.env['ems.create.project.wizard'].with_context(default_lead_id=lead.id).create({})
        wiz.action_confirm()
        self.assertTrue(lead.ems_project_id)
        self.assertEqual(lead.ems_project_id.ems_proposal_id, lead)

    def test_po_sub_budget_check_and_loa(self):
        prod = self.env.ref('ems_register.product_subconsultancy').product_variant_id
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id, 'ems_project_id': self.project.id,
            'order_line': [(0, 0, {'name': 'Review', 'product_qty': 1, 'price_unit': 20000, 'product_id': prod.id})],
        })
        po.action_issue_loa()
        self.assertTrue(po.ems_loa_ref)
        self.assertEqual(po.state, 'sent')
        with self.assertRaises(UserError):
            po.button_confirm()
        po.order_line.price_unit = 8000
        po.button_confirm()
        self.assertEqual(self.project.ems_committed, 8000)
        self.assertEqual(self.project.ems_sub_balance, 2000)

    def test_fee_stage_invoice(self):
        stage = self.env['ems.fee.stage'].create({
            'project_id': self.project.id, 'name': 'M1', 'percent': 25})
        self.assertEqual(stage.amount, 25000)
        with self.assertRaises(UserError):
            stage.action_invoice_stage()
        stage.eligible = True
        stage.action_invoice_stage()
        self.assertEqual(stage.state, 'invoiced')
        self.assertEqual(stage.invoice_ids.ems_project_id, self.project)

    def test_allocation_hours_cost_and_rates_group(self):
        grade = self.env['ems.grade'].create({'code': 'T1', 'name': 'T', 'cost_rate': 100})
        emp = self.env['hr.employee'].create({'name': 'Emp', 'ems_grade_id': grade.id})
        alloc = self.env['ems.allocation'].create({
            'name': 'Work', 'employee_id': emp.id, 'project_id': self.project.id,
            'date_from': '2025-09-15', 'date_to': '2025-09-19', 'hours_per_day': 4})
        self.assertEqual(alloc.days, 5)
        self.assertEqual(alloc.hours, 20)
        self.assertEqual(alloc.cost, 2000)
        self.assertFalse(alloc.overbooked)
        self.env['ems.allocation'].create({
            'name': 'Extra', 'employee_id': emp.id, 'project_id': self.project.id,
            'date_from': '2025-09-15', 'date_to': '2025-09-15', 'hours_per_day': 6})
        alloc.invalidate_recordset()
        self.assertTrue(alloc.overbooked)

    def test_offer_to_employee(self):
        offer = self.env['ems.offer'].create({'candidate': 'New Hire', 'salary_basic': 10000})
        self.assertNotEqual(offer.name, 'New')
        offer.action_accept()
        offer.action_create_employee()
        self.assertEqual(offer.employee_id.name, 'New Hire')
