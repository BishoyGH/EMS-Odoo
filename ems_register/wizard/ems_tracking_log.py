import base64
import io

import xlsxwriter

from odoo import fields, models, _

COLUMNS = [
    ('PO No.', lambda po: po.name),
    ('LOA Ref.', lambda po: po.ems_loa_ref or ''),
    ('LOA Rev.', lambda po: po.ems_loa_revision),
    ('Status', lambda po: dict(po._fields['state'].selection).get(po.state, po.state)),
    ('Vendor', lambda po: po.partner_id.name or ''),
    ('Project Code', lambda po: po.ems_project_id.ems_code or ''),
    ('Project', lambda po: po.ems_project_id.name or ('Office Overhead' if getattr(po, 'ems_overhead', False) else '')),
    ('Client', lambda po: po.ems_project_id.partner_id.name or ''),
    ('Quotation Ref.', lambda po: po.ems_quotation_ref or ''),
    ('Quotation Date', lambda po: po.ems_quotation_date or ''),
    ('Order Date', lambda po: po.date_order.date() if po.date_order else ''),
    ('LOA Date', lambda po: po.ems_loa_date or ''),
    ('Currency', lambda po: po.currency_id.name),
    ('Amount ex VAT', lambda po: po.amount_untaxed),
    ('VAT', lambda po: po.amount_tax),
    ('Total', lambda po: po.amount_total),
    ('Advance %', lambda po: po.ems_advance_pct),
    ('Retention %', lambda po: po.ems_retention_pct),
    ('Payment Days', lambda po: po.ems_payment_days),
    ('Milestones', lambda po: len(po.ems_milestone_ids)),
    ('Signed', lambda po: 'Yes' if po.ems_signed else 'No'),
    ('Signed By', lambda po: po.ems_signed_by or ''),
    ('Start Date', lambda po: po.ems_date_start or ''),
    ('Duration', lambda po: ('%s %s' % (po.ems_duration, po.ems_duration_unit)) if po.ems_duration else ''),
    ('Governing Law', lambda po: po.ems_governing_law or ''),
    ('Forum', lambda po: po.ems_forum or ''),
    ('Follow-up Date', lambda po: po.ems_follow_up_date or ''),
    ('Next Action', lambda po: po.ems_next_action or ''),
    ('Prints', lambda po: po.ems_print_count),
    ('Document Location', lambda po: po.ems_document_location or ''),
]


class EmsTrackingLogWizard(models.TransientModel):
    _name = 'ems.tracking.log.wizard'
    _description = 'Export Tracking Log'

    date_from = fields.Date('From')
    date_to = fields.Date('To')
    project_id = fields.Many2one('project.project', 'Project')
    state = fields.Selection([('purchase', 'Confirmed only'), ('all', 'All orders')], default='all', required=True)
    file = fields.Binary(readonly=True)
    filename = fields.Char(readonly=True)

    def action_export(self):
        self.ensure_one()
        domain = []
        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_order', '<=', fields.Datetime.to_datetime(self.date_to).replace(hour=23, minute=59)))
        if self.project_id:
            domain.append(('ems_project_id', '=', self.project_id.id))
        if self.state == 'purchase':
            domain.append(('state', 'in', ('purchase', 'done')))
        orders = self.env['purchase.order'].search(domain, order='date_order, id')
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'default_date_format': 'yyyy-mm-dd'})
        ws = wb.add_worksheet('Tracking Log')
        head = wb.add_format({'bold': True, 'bg_color': '#1F3864', 'font_color': 'white', 'border': 1})
        money = wb.add_format({'num_format': '#,##0.00'})
        for col, (title, _fn) in enumerate(COLUMNS):
            ws.write(0, col, title, head)
            ws.set_column(col, col, max(len(title) + 2, 14))
        for row, po in enumerate(orders, 1):
            for col, (title, fn) in enumerate(COLUMNS):
                value = fn(po)
                if hasattr(value, 'isoformat'):
                    ws.write_datetime(row, col, fields.Datetime.to_datetime(value) if not hasattr(value, 'hour') else value)
                elif isinstance(value, float):
                    ws.write_number(row, col, value, money)
                else:
                    ws.write(row, col, value)
        ws.freeze_panes(1, 2)
        ws.autofilter(0, 0, max(len(orders), 1), len(COLUMNS) - 1)
        wb.close()
        self.write({'file': base64.b64encode(buf.getvalue()).decode(),
                    'filename': 'EMS_Tracking_Log_%s.xlsx' % fields.Date.today()})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}
