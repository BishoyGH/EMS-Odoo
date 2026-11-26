import base64
import os
import sqlite3
import tempfile

from odoo.tests import TransactionCase, tagged

SCHEMA = os.path.join(os.path.dirname(__file__), 'legacy_schema.sql')


@tagged('post_install', '-at_install')
class TestEmsMigration(TransactionCase):
    """Runs the .dat migration against a small synthetic backup (the real file is confidential)."""

    @classmethod
    def _build_backup(cls):
        fd, path = tempfile.mkstemp(suffix='.dat')
        os.close(fd)
        conn = sqlite3.connect(path)
        with open(SCHEMA) as handle:
            conn.executescript(handle.read())
        conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', '2')")
        conn.execute("INSERT INTO x_grade(id, code, name, sequence) VALUES (1, 'A', 'Grade A', 10)")
        conn.execute("INSERT INTO res_partner(id, name, company_type, x_category, supplier_rank, customer_rank, vat, "
                     "country_code, x_contact_name, x_contact_email) "
                     "VALUES (1, 'Legacy Client LLC', 'company', 'Company / legal entity', 0, 1, '123-not-a-vat', 'AE', "
                     "'Jane Contact', 'jane@example.com')")
        conn.execute("INSERT INTO hr_employee(id, name, x_code, grade_id, department, employment_type, x_hours_week, "
                     "x_plannable, active) VALUES (1, 'Legacy Engineer', 'E1', 1, 'Engineering', 'Full-time', 40, 1, 1)")
        conn.execute("INSERT INTO crm_lead(id, x_number, x_seq, x_category, name, partner_id, stage, expected_revenue, "
                     "x_awarded_value, currency_id) VALUES (1, 'P99001', 1, 'Design', 'Legacy Tower', 1, 'won', 100000, 0, 'AED')")
        conn.execute("INSERT INTO crm_lead(id, x_number, x_seq, x_category, name, partner_id, stage, expected_revenue, "
                     "x_awarded_value, currency_id) VALUES (2, 'P99002', 2, 'Design', 'Legacy Tower', 1, 'lost', 5000, 0, 'AED')")
        conn.execute("INSERT INTO crm_lead_revision(id, lead_id, revision, date, amount) VALUES (1, 1, 'R00', '2025-01-01', 100000)")
        conn.execute("INSERT INTO project_project(id, x_code, name, partner_id, x_contract_value, stage, active) "
                     "VALUES (1, '25-9001', 'Legacy Tower Project', 1, 100000, 'In Progress', 1)")
        conn.execute("INSERT INTO x_fee_stage(id, project_id, sequence, name, percent, basis, amount) "
                     "VALUES (1, 1, 10, 'M1', 40, 0, 40000)")
        conn.execute("INSERT INTO x_client_invoice(id, project_id, stage_id, partner_id, name, invoice_date, invoice_date_due, "
                     "amount_untaxed, amount_tax, amount_total, x_amount_paid, x_payment_date, payment_state, state) "
                     "VALUES (1, 1, 1, 1, 'INV-1', '2025-02-01', '2025-03-01', 40000, 2000, 42000, 42000, '2025-02-20', 'paid', 'posted')")
        conn.execute("INSERT INTO x_client_invoice(id, project_id, stage_id, partner_id, name, invoice_date, invoice_date_due, "
                     "amount_untaxed, amount_tax, amount_total, x_amount_paid, payment_state, state) "
                     "VALUES (2, 1, NULL, 1, 'INV-2', '2025-03-01', '2025-04-01', 10000, 500, 10500, 0, 'not_paid', 'posted')")
        conn.execute("INSERT INTO mail_message(id, model, res_id, date, kind, body, author) "
                     "VALUES (1, 'project_project', 1, '2025-01-05 10:00:00', 'notification', 'Record created', 'Admin')")
        conn.commit()
        conn.close()
        return path

    def test_migration_is_complete_and_rerunnable(self):
        path = self._build_backup()
        self.addCleanup(os.unlink, path)
        with open(path, 'rb') as handle:
            content = base64.b64encode(handle.read()).decode()
        run = self.env['ems.migration.run'].create({'file': content, 'filename': 'backup.dat'})
        run.action_run()
        self.assertEqual(run.state, 'done')
        summary = {s.table: s for s in run.summary_ids}
        self.assertEqual(summary['res_partner'].created, 1)
        self.assertEqual(summary['crm_lead'].created, 2)
        self.assertEqual(summary['x_client_invoice'].created, 2)
        self.assertEqual(sum(summary[t].failed for t in summary), 0)

        project = self.env['project.project'].search([('ems_code', '=', '25-9001')])
        self.assertEqual(project.ems_contract_value, 100000)
        self.assertEqual(project.stage_id.name, 'In Progress')
        self.assertEqual(len(project.ems_fee_stage_ids), 1)
        invoices = self.env['account.move'].search([('ems_project_id', '=', project.id)])
        self.assertEqual(len(invoices), 2)
        self.assertEqual(sorted(invoices.mapped('payment_state')), ['not_paid', 'paid'])
        self.assertEqual(sorted(invoices.mapped('amount_total')), [10500, 42000])
        partner = self.env['res.partner'].search([('name', '=', 'Legacy Client LLC')])
        self.assertEqual(partner.child_ids.name, 'Jane Contact')
        self.assertEqual(partner.ems_client_payment_days, 30)
        employee = self.env['hr.employee'].search([('name', '=', 'Legacy Engineer')])
        self.assertEqual(employee.ems_grade_id.code, 'A')
        self.assertTrue(project.message_ids.filtered(lambda m: 'Record created' in (m.body or '')))
        lost = self.env['crm.lead'].with_context(active_test=False).search([('ems_number', '=', 'P99002')])
        self.assertFalse(lost.active)

        codes = set(run.issue_ids.mapped('code'))
        self.assertTrue({'project_no_proposal', 'won_zero_award', 'duplicate_lead', 'fee_not_100',
                         'rates_vault', 'unpaid_invoices'} <= codes, codes)

        # running again updates instead of duplicating
        run.action_run()
        self.assertEqual(self.env['project.project'].search_count([('ems_code', '=', '25-9001')]), 1)
        self.assertEqual(self.env['account.move'].search_count([('ems_project_id', '=', project.id)]), 2)
        self.assertEqual(self.env['crm.lead'].with_context(active_test=False).search_count(
            [('ems_number', 'in', ('P99001', 'P99002'))]), 2)

    def test_excel_import_templates(self):
        wizard = self.env['ems.import.wizard'].create({'kind': 'fee_stages'})
        wizard.action_download_template()
        self.assertTrue(wizard.template_file)
        project = self.env['project.project'].create({'name': 'Import Project', 'ems_contract_value': 200000})
        import io

        import xlsxwriter
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        ws = wb.add_worksheet('Milestones and Revenue')
        for col, head in enumerate(['Project Code *', 'Stage *', 'Trigger Evidence', 'Percent', 'Fixed Amount']):
            ws.write(0, col, head)
        ws.write_row(1, 0, [project.ems_code, 'M1', 'Acceptance AND NTP', 0.25])
        ws.write_row(2, 0, ['UNKNOWN', 'M2', 'x', 0.5])
        wb.close()
        wizard.write({'file': base64.b64encode(buf.getvalue()).decode(), 'filename': 'fees.xlsx'})
        wizard.action_import()
        self.assertEqual(project.ems_fee_stage_ids.amount, 50000)
        self.assertIn('1 rows imported, 1 rows rejected', wizard.result)
