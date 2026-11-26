from datetime import date, timedelta

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmsReports(TransactionCase):
    """Every EMS printout renders on the shared letterhead and shows its key data."""

    def _html(self, xmlid, records):
        report = self.env.ref(xmlid)
        return report._render_qweb_html(report.report_name, records.ids)[0].decode()

    def test_purchase_order_and_loa(self):
        vendor = self.env['res.partner'].create({'name': 'Rep Vendor', 'vat': 'TRN123'})
        po = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'ems_loa_ref': 'EMS-LOA-26-0001', 'ems_governing_law': 'UAE law',
            'ems_advance_pct': 10, 'ems_payment_days': 30,
            'ems_milestone_ids': [Command.create({'name': 'Advance', 'percent': 100})],
            'order_line': [Command.create({'name': 'Review piling', 'product_qty': 1, 'price_unit': 92000})],
        })
        html = self._html('ems_register.action_report_ems_po', po)
        for needle in ('PURCHASE ORDER', 'Rep Vendor', 'TRN123', 'Review piling', 'Amount in words', 'Accepted by the Vendor'):
            self.assertIn(needle, html)
        html = self._html('ems_register.action_report_ems_loa', po)
        for needle in ('LETTER OF APPOINTMENT', 'EMS-LOA-26-0001', 'UAE law', 'Advance', 'Payment milestones'):
            self.assertIn(needle, html)

    def test_offer_letter_hides_salary_without_rates_group(self):
        offer = self.env['ems.offer'].create({'candidate': 'Ann Candidate', 'salary_basic': 12345})
        html = self._html('ems_people.action_report_ems_offer', offer)
        self.assertIn('OFFER OF EMPLOYMENT', html)
        self.assertIn('Ann Candidate', html)
        self.assertNotIn('Monthly package', html)
        self.env.user.group_ids = [Command.link(self.env.ref('ems_base.group_ems_rates').id)]
        html = self._html('ems_people.action_report_ems_offer', offer.with_user(self.env.user))
        self.assertIn('Monthly package', html)

    def test_customer_statement_aging(self):
        partner = self.env['res.partner'].create({'name': 'Stmt Client', 'customer_rank': 1})
        today = date.today()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': partner.id,
            'invoice_date': today - timedelta(days=50), 'invoice_date_due': today - timedelta(days=40),
            'invoice_line_ids': [Command.create({'name': 'Fee', 'quantity': 1, 'price_unit': 1000})],
        })
        invoice.action_post()
        values = self.env['report.ems_payments.report_ems_statement']._get_report_values(partner.ids)
        st = values['statements'][partner.id]
        self.assertEqual(st['total'], 1000)
        self.assertEqual(st['buckets'], [0, 0, 1000, 0, 0], '40 days late falls in 31-60')
        self.assertEqual(st['rows'][0]['late'], 40)
        html = self._html('ems_payments.action_report_ems_statement', partner)
        self.assertIn('CUSTOMER STATEMENT', html)
        self.assertIn('Total outstanding', html)

    def test_weekly_plan_one_page_per_person_with_day_columns(self):
        project = self.env['project.project'].create({'name': 'Plan Project'})
        emp = self.env['hr.employee'].create({'name': 'Plan Emp'})
        monday = date.today() - timedelta(days=date.today().weekday())
        self.env['ems.allocation'].create({
            'name': 'Model checks', 'employee_id': emp.id, 'project_id': project.id,
            'date_from': monday + timedelta(days=3), 'date_to': monday + timedelta(days=4), 'hours_per_day': 2})
        wizard = self.env['ems.weekly.plan.wizard'].create({'week_start': monday})
        values = self.env['report.ems_planning.report_weekly_plan']._get_report_values(wizard.ids)
        plan = next(p for p in values['plans'] if p['employee'] == emp)
        self.assertEqual(plan['rows'][0]['cells'], [0, 0, 0, 2, 2])
        self.assertEqual(plan['total'], 4)
        html = self._html('ems_planning.action_report_weekly_plan', wizard)
        self.assertIn('WEEKLY ACTION PLAN', html)
        self.assertIn('Model checks', html)


@tagged('post_install', '-at_install')
class TestEmsPlannerMove(TransactionCase):
    """Backend of the drag-and-drop planner."""

    def setUp(self):
        super().setUp()
        self.project = self.env['project.project'].create({'name': 'Drag Project'})
        self.a = self.env['hr.employee'].create({'name': 'Drag A', 'ems_plannable': True})
        self.b = self.env['hr.employee'].create({'name': 'Drag B', 'ems_plannable': True})
        self.monday = date.today() - timedelta(days=date.today().weekday())
        self.alloc = self.env['ems.allocation'].create({
            'name': 'Drag me', 'employee_id': self.a.id, 'project_id': self.project.id,
            'date_from': self.monday, 'date_to': self.monday + timedelta(days=4), 'hours_per_day': 4})

    def test_planner_data_has_chip(self):
        data = self.env['ems.allocation'].get_planner_data(self.monday, 4)
        row = next(r for r in data['rows'] if r['id'] == self.a.id)
        self.assertEqual([c['id'] for c in row['cells'][0]['chips']], [self.alloc.id])

    def test_move_to_other_person_and_week(self):
        self.env['ems.allocation'].move_allocation(self.alloc.id, self.b.id, 2)
        self.assertEqual(self.alloc.employee_id, self.b)
        self.assertEqual(self.alloc.date_from, self.monday + timedelta(weeks=2))
        self.assertEqual(self.alloc.date_to, self.monday + timedelta(weeks=2, days=4))
        data = self.env['ems.allocation'].get_planner_data(self.monday, 4)
        row = next(r for r in data['rows'] if r['id'] == self.b.id)
        self.assertTrue(row['cells'][2]['chips'])
        self.assertFalse(next(r for r in data['rows'] if r['id'] == self.a.id)['cells'][0]['chips'])


@tagged('post_install', '-at_install')
class TestEmsPlannerTour(HttpCase):
    def test_planner_drag_and_drop_tour(self):
        project = self.env['project.project'].create({'name': 'Tour Drag Project'})
        a = self.env['hr.employee'].create({'name': 'Tour Person A', 'ems_plannable': True})
        b = self.env['hr.employee'].create({'name': 'Tour Person B', 'ems_plannable': True})
        monday = date.today() - timedelta(days=date.today().weekday())
        alloc = self.env['ems.allocation'].create({
            'name': 'Tour bar', 'employee_id': a.id, 'project_id': project.id,
            'date_from': monday, 'date_to': monday + timedelta(days=4), 'hours_per_day': 4})
        self.start_tour('/odoo/action-ems_planning.action_ems_planner_grid', 'ems_planner_drag_tour', login='admin')
        alloc.invalidate_recordset()
        self.assertEqual(alloc.employee_id, b)
        self.assertEqual(alloc.date_from, monday + timedelta(weeks=1))
