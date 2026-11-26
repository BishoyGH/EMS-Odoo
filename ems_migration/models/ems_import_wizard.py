import base64
import io

import openpyxl
import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# kind -> (sheet title, [(column, required, description)])
TEMPLATES = {
    'clients': ('Clients and Vendors', [
        ('Name', True, 'Legal name of the client or vendor. Existing names are updated, not duplicated.'),
        ('Role', True, 'Client, Vendor or Both.'),
        ('Email', False, 'Main email.'), ('Phone', False, 'Main phone.'),
        ('Sector', False, 'Business sector.'),
        ('Payment Days', False, 'Client payment terms in days (default 30).'),
        ('Trade Licence No.', False, 'Trade licence number (vendors).'),
    ]),
    'fee_stages': ('Milestones and Revenue', [
        ('Project Code', True, 'EMS project code, for example 25-1026.'),
        ('Stage', True, 'Billing milestone name, for example M1.'),
        ('Trigger Evidence', False, 'Evidence that releases the invoice, for example Acceptance of offer AND NTP.'),
        ('Percent', False, 'Percent of contract (0.25 or 25 both accepted).'),
        ('Fixed Amount', False, 'Use instead of Percent for a fixed amount ex VAT.'),
    ]),
    'resource_plan': ('Resource Plan', [
        ('Project Code', True, 'EMS project code.'),
        ('Employee', True, 'Employee name as in Odoo.'),
        ('Hours per Week', True, 'Planned hours per week (the planner stores hours per day = this / 5).'),
        ('Date From', True, 'YYYY-MM-DD.'), ('Date To', True, 'YYYY-MM-DD.'),
        ('Tentative', False, 'Yes or No.'), ('Task', False, 'Action or task name.'),
    ]),
    'timesheets': ('Timesheet Import', [
        ('Entry ID', False, 'Your own reference, kept in the description.'),
        ('Date', True, 'YYYY-MM-DD.'), ('Employee', True, 'Employee name as in Odoo.'),
        ('Project Code', True, 'EMS project code.'),
        ('WBS', True, 'P0 to P7 stage of the project.'),
        ('Activity', True, 'Description of the work (mandatory).'),
        ('Hours', True, 'Hours worked, positive and not above 24.'),
        ('Billable', False, 'Yes or No.'),
    ]),
    'vendor_costs': ('Vendor and Cost Import', [
        ('Vendor', True, 'Vendor name as in Odoo (created when missing).'),
        ('Project or Office Overhead', True, 'EMS project code, or the words Office Overhead.'),
        ('PO Reference', False, 'Vendor quotation / PO reference.'),
        ('Scope', True, 'What is bought.'),
        ('Committed ex VAT', True, 'Order value ex VAT.'),
    ]),
}


def _yes(value):
    return str(value or '').strip().lower() in ('yes', 'y', 'true', '1')


class EmsImportWizard(models.TransientModel):
    _name = 'ems.import.wizard'
    _description = 'EMS Excel Import Templates'

    kind = fields.Selection([(k, v[0]) for k, v in TEMPLATES.items()], required=True, default='clients')
    file = fields.Binary('Filled Template (.xlsx)')
    filename = fields.Char()
    template_file = fields.Binary(readonly=True)
    template_filename = fields.Char(readonly=True)
    result = fields.Text(readonly=True)

    # ------------------------------------------------------------ template + dictionary
    def action_download_template(self):
        self.ensure_one()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        head = wb.add_format({'bold': True, 'bg_color': '#1F3864', 'font_color': 'white', 'border': 1})
        req = wb.add_format({'bold': True, 'bg_color': '#C00000', 'font_color': 'white', 'border': 1})
        title, columns = TEMPLATES[self.kind]
        ws = wb.add_worksheet(title[:31])
        for idx, (col, required, _desc) in enumerate(columns):
            ws.write(0, idx, col + (' *' if required else ''), req if required else head)
            ws.set_column(idx, idx, max(len(col) + 4, 16))
        ws.freeze_panes(1, 0)
        dd = wb.add_worksheet('Data Dictionary')
        for idx, label in enumerate(('Column', 'Required', 'Description')):
            dd.write(0, idx, label, head)
        for row, (col, required, desc) in enumerate(columns, 1):
            dd.write(row, 0, col)
            dd.write(row, 1, 'Yes' if required else 'No')
            dd.write(row, 2, desc)
        dd.set_column(0, 0, 30)
        dd.set_column(2, 2, 90)
        wb.close()
        self.write({'template_file': base64.b64encode(buf.getvalue()).decode(),
                    'template_filename': 'EMS_import_%s.xlsx' % self.kind})
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    # ------------------------------------------------------------ import
    def _rows(self):
        wb = openpyxl.load_workbook(io.BytesIO(self.file.content), data_only=True, read_only=True)
        title, columns = TEMPLATES[self.kind]
        ws = wb[title[:31]] if title[:31] in wb.sheetnames else wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        header = [str(h or '').replace('*', '').strip() for h in next(rows)]
        for number, values in enumerate(rows, 2):
            if not any(v not in (None, '') for v in values):
                continue
            yield number, dict(zip(header, values))

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Upload the filled template first.'))
        handler = getattr(self, '_import_%s' % self.kind)
        ok, errors = 0, []
        for number, row in self._rows():
            try:
                with self.env.cr.savepoint():
                    handler(row)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(_('Row %(n)s: %(e)s', n=number, e=exc))
        self.result = _('%(ok)s rows imported, %(bad)s rows rejected.', ok=ok, bad=len(errors)) + (
            '\n' + '\n'.join(errors) if errors else '')
        for err in errors:
            self.env['ems.data.issue'].create({'name': err, 'severity': '3_medium', 'code': 'import_row',
                                               'source': self.filename or self.kind})
        return self._reopen()

    def _project(self, code):
        code = str(code or '').strip()
        project = self.env['project.project'].search([('ems_code', '=', code)], limit=1)
        if not project:
            raise UserError(_('Unknown project code "%s".') % code)
        return project

    def _employee(self, name):
        name = str(name or '').strip()
        emp = self.env['hr.employee'].search([('name', '=ilike', name)], limit=1)
        if not emp:
            raise UserError(_('Unknown employee "%s".') % name)
        return emp

    def _import_clients(self, row):
        name = str(row.get('Name') or '').strip()
        if not name:
            raise UserError(_('Name is required.'))
        role = str(row.get('Role') or 'Client').strip().lower()
        vals = {'name': name, 'is_company': True, 'email': row.get('Email') or False, 'phone': row.get('Phone') or False,
                'ems_sector': row.get('Sector') or False, 'ems_licence_no': row.get('Trade Licence No.') or False}
        if role in ('client', 'both'):
            vals['customer_rank'] = 1
            vals['ems_client_payment_days'] = int(row.get('Payment Days') or 30)
        if role in ('vendor', 'both'):
            vals['supplier_rank'] = 1
        partner = self.env['res.partner'].search([('name', '=ilike', name)], limit=1)
        if partner:
            partner.write(vals)
        else:
            self.env['res.partner'].create(vals)

    def _import_fee_stages(self, row):
        project = self._project(row.get('Project Code'))
        percent = float(row.get('Percent') or 0.0)
        if 0 < percent <= 1.0:
            percent *= 100.0
        vals = {'project_id': project.id, 'name': str(row.get('Stage') or '').strip(),
                'trigger': row.get('Trigger Evidence') or False}
        if not vals['name']:
            raise UserError(_('Stage is required.'))
        if row.get('Fixed Amount'):
            vals.update(basis='fixed', amount=float(row['Fixed Amount']))
        else:
            vals.update(basis='percent', percent=percent)
        stage = self.env['ems.fee.stage'].search([('project_id', '=', project.id), ('name', '=', vals['name'])], limit=1)
        if stage:
            stage.write(vals)
        else:
            self.env['ems.fee.stage'].create(vals)

    def _import_resource_plan(self, row):
        project = self._project(row.get('Project Code'))
        emp = self._employee(row.get('Employee'))
        hours_week = float(row.get('Hours per Week') or 0.0)
        self.env['ems.allocation'].create({
            'name': row.get('Task') or project.name, 'employee_id': emp.id, 'project_id': project.id,
            'date_from': fields.Date.to_date(row.get('Date From')), 'date_to': fields.Date.to_date(row.get('Date To')),
            'hours_per_day': hours_week / 5.0, 'tentative': _yes(row.get('Tentative')),
        })

    def _import_timesheets(self, row):
        project = self._project(row.get('Project Code'))
        emp = self._employee(row.get('Employee'))
        wbs = str(row.get('WBS') or '').strip().upper()
        task = self.env['project.task'].search([('project_id', '=', project.id), ('ems_wbs_code', '=', wbs)], limit=1)
        if not task:
            raise UserError(_('Project %(p)s has no WBS stage "%(w)s". Apply the WBS template first.',
                              p=project.display_name, w=wbs))
        activity = str(row.get('Activity') or '').strip()
        if row.get('Entry ID'):
            activity = '%s [%s]' % (activity, row['Entry ID'])
        self.env['account.analytic.line'].create({
            'project_id': project.id, 'task_id': task.id, 'employee_id': emp.id, 'name': activity,
            'unit_amount': float(row.get('Hours') or 0.0), 'date': fields.Date.to_date(row.get('Date')),
        })

    def _import_vendor_costs(self, row):
        name = str(row.get('Vendor') or '').strip()
        vendor = self.env['res.partner'].search([('name', '=ilike', name)], limit=1) or self.env['res.partner'].create({
            'name': name, 'is_company': True, 'supplier_rank': 1})
        target = str(row.get('Project or Office Overhead') or '').strip()
        vals = {'partner_id': vendor.id, 'partner_ref': row.get('PO Reference') or False}
        if target.lower() == 'office overhead':
            vals['ems_overhead'] = True
        else:
            vals['ems_project_id'] = self._project(target).id
        product = self.env.ref('ems_register.product_subconsultancy').product_variant_id
        vals['order_line'] = [(0, 0, {'product_id': product.id, 'name': row.get('Scope') or 'Imported commitment',
                                      'product_qty': 1, 'price_unit': float(row.get('Committed ex VAT') or 0.0)})]
        self.env['purchase.order'].create(vals)
