import base64
import logging
import os
import re
import sqlite3
import tempfile
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

XMLID_MODULE = '__import__'

LEAD_STAGES = {
    'rfp': 'RFP Received', 'submitted': 'Proposal Submitted', 'won': 'Won', 'completed': 'Won',
    'lost': 'Lost to competitor', 'regret': 'Regret (we declined)', 'cancelled': 'Cancelled by client',
    'on_hold': 'On Hold',
}
METHODS = {'email': 'email', 'call': 'call', 'meeting': 'meeting', 'whatsapp': 'whatsapp'}
CATEGORY = {'3rd party': '3p', 'design': 'design', 'supervision': 'supervision'}
PARTNER_CATEGORY = {'company / legal entity': 'company', 'licensed freelancer': 'freelancer',
                    'individual consultant': 'individual'}
EMPLOYMENT = {'full-time': 'full', 'part-time': 'part', 'contractor': 'contract', 'freelancer': 'freelance',
              'vendor': 'contract'}
DOC_CATEGORY = {'trade licence': 'licence', 'insurance certificate': 'insurance', 'bank letter': 'bank',
                'generated document': 'generated', 'other': 'other'}
CHATTER_MODELS = {
    'res_partner': 'res.partner', 'project_project': 'project.project', 'crm_lead': 'crm.lead',
    'purchase_order': 'purchase.order', 'x_client_invoice': 'account.move', 'hr_employee': 'hr.employee',
    'x_offer': 'ems.offer', 'x_project_milestone': 'project.milestone',
}
TABLE_MODEL = {
    'res_partner': 'res.partner', 'project_project': 'project.project', 'crm_lead': 'crm.lead',
    'purchase_order': 'purchase.order', 'x_client_invoice': 'account.move', 'hr_employee': 'hr.employee',
    'x_offer': 'ems.offer', 'x_project_milestone': 'project.milestone',
}


def _s(value):
    """Clean a sqlite value: empty strings become False."""
    if value is None:
        return False
    if isinstance(value, str):
        value = value.strip()
        return value or False
    return value


def _int(value, default=0):
    digits = re.sub(r'\D', '', str(value)) if value not in (None, '') else ''
    return int(digits) if digits else default


def _date(value):
    value = _s(value)
    return value[:10] if value else False


class EmsMigrationRun(models.Model):
    """Re-runnable import of the EMS_PO_Register .dat backup (SQLite, schema v2).

    The backup is opened read-only. Every record is keyed by the external id
    ``__import__.ems_<table>_<id>`` (the same ids the exe's "Export for Odoo" used), so
    running the migration again updates instead of duplicating.
    The encrypted rates vault is never read: cost rates are entered in Odoo by the Rates Manager.
    """
    _name = 'ems.migration.run'
    _description = 'EMS .dat Migration Run'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(default=lambda s: 'Migration %s' % fields.Datetime.now(), required=True)
    file = fields.Binary('.dat Backup', attachment=True, required=True)
    filename = fields.Char()
    include_chatter = fields.Boolean('Import chatter history', default=True)
    include_invoices = fields.Boolean('Import client invoices (post and register payments)', default=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'), ('failed', 'Failed')], default='draft',
                             tracking=True)
    log = fields.Text(readonly=True)
    summary_ids = fields.One2many('ems.migration.summary', 'run_id', readonly=True)
    issue_ids = fields.One2many('ems.data.issue', 'run_id', readonly=True)
    issue_count = fields.Integer(compute='_compute_issue_count')

    @api.depends('issue_ids')
    def _compute_issue_count(self):
        for run in self:
            run.issue_count = len(run.issue_ids)

    # ------------------------------------------------------------------ helpers
    def _xid(self, table, legacy_id):
        return 'ems_%s_%s' % (table, legacy_id)

    def _ref(self, table, legacy_id):
        """Odoo id for a legacy row, or False."""
        if not legacy_id:
            return False
        rec = self.env['ir.model.data'].sudo().search([
            ('module', '=', XMLID_MODULE), ('name', '=', self._xid(table, legacy_id))], limit=1)
        return rec.res_id if rec else False

    def _upsert(self, model, table, legacy_id, vals, counters):
        """Create or update the record for a legacy row. A bad row becomes a data issue, not a failed run."""
        data = self.env['ir.model.data'].sudo()
        xml = data.search([('module', '=', XMLID_MODULE), ('name', '=', self._xid(table, legacy_id))], limit=1)
        record = self.env[model].browse(xml.res_id).exists() if xml else self.env[model]
        try:
            with self.env.cr.savepoint():
                if record:
                    record.write(vals)
                    counters['updated'] += 1
                else:
                    record = self.env[model].create(vals)
                    if xml:
                        xml.res_id = record.id
                    else:
                        data.create({'module': XMLID_MODULE, 'name': self._xid(table, legacy_id),
                                     'model': model, 'res_id': record.id, 'noupdate': True})
                    counters['created'] += 1
        except Exception as exc:  # noqa: BLE001
            counters['failed'] += 1
            self._issue(_('Row %(t)s #%(i)s (%(n)s) was not migrated: %(e)s', t=table, i=legacy_id,
                          n=vals.get('name') or vals.get('candidate') or '', e=str(exc).strip()[:300]),
                        '2_high', 'row_failed', source=table)
            return self.env[model]
        return record

    def _issue(self, name, severity, code, record=None, source=False, resolution=False):
        vals = {'name': name, 'severity': severity, 'code': code, 'run_id': self.id,
                'source': source, 'resolution': resolution}
        if record:
            vals.update(res_model=record._name, res_id=record.id, record_name=record.display_name)
        return self.env['ems.data.issue'].create(vals)

    # ------------------------------------------------------------------ main entry
    def action_run(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Upload the .dat backup first.'))
        self.issue_ids.unlink()
        self.summary_ids.unlink()
        fd, path = tempfile.mkstemp(suffix='.dat')
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(self.file.content)
            conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
            conn.row_factory = sqlite3.Row
            try:
                version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                if not version or str(version[0]) != '2':
                    raise UserError(_('Unsupported backup: expected schema version 2.'))
                self = self.with_context(
                    tracking_disable=True, mail_create_nosubscribe=True, mail_auto_subscribe_no_notify=True,
                    mail_notrack=True, ems_no_audit=True, ems_skip_approval=True, ems_timesheet_system=True,
                    mail_activity_quick_update=True, no_vat_validation=True)
                self._migrate(conn)
            finally:
                conn.close()
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.exception('EMS migration failed')
            self.write({'state': 'failed', 'log': '%s\n%s' % (self.log or '', exc)})
            raise
        finally:
            os.unlink(path)
        return self.action_view_issues()

    def _migrate(self, conn):
        steps = [
            ('x_grade', self._m_grades), ('res_partner', self._m_partners), ('x_hr_role', self._m_roles),
            ('hr_employee', self._m_employees), ('x_service_item', self._m_service_items),
            ('crm_lead', self._m_leads), ('crm_lead_revision', self._m_revisions),
            ('project_project', self._m_projects), ('x_fee_stage', self._m_fee_stages),
            ('x_client_invoice', self._m_invoices), ('purchase_order', self._m_purchase_orders),
            ('x_project_service', self._m_services), ('x_project_milestone', self._m_milestones),
            ('x_allocation', self._m_allocations), ('x_offer', self._m_offers),
            ('ir_attachment', self._m_attachments), ('mail_message', self._m_chatter),
        ]
        for table, func in steps:
            counters = defaultdict(int)
            if table == 'x_client_invoice' and not self.include_invoices:
                continue
            if table == 'mail_message' and not self.include_chatter:
                continue
            try:
                with self.env.cr.savepoint():
                    func(conn, counters)
            except Exception as exc:  # noqa: BLE001
                _logger.exception('migration step %s', table)
                self._issue(_('Step %(t)s failed: %(e)s', t=table, e=exc), '1_critical', 'step_failed')
                counters['failed'] += 1
            self.env['ems.migration.summary'].create({
                'run_id': self.id, 'table': table, 'created': counters['created'],
                'updated': counters['updated'], 'skipped': counters['skipped'], 'failed': counters['failed']})
        self._link_proposals_to_projects(conn)
        self._detect_issues(conn)
        self.write({'state': 'done', 'log': _('Finished: %s data issues found.') % len(self.issue_ids)})

    # ------------------------------------------------------------------ steps
    def _m_grades(self, conn, c):
        for r in conn.execute('SELECT * FROM x_grade'):
            self._upsert('ems.grade', 'x_grade', r['id'], {
                'code': r['code'], 'name': r['name'], 'sequence': r['sequence'] or 10}, c)

    def _country(self, code):
        code = _s(code)
        return self.env['res.country'].search([('code', '=', code.upper())], limit=1).id if code else False

    def _m_partners(self, conn, c):
        for r in conn.execute('SELECT * FROM res_partner ORDER BY id'):
            vals = {
                'name': r['name'], 'is_company': r['company_type'] != 'person', 'ref': _s(r['ref']),
                'vat': _s(r['vat']), 'country_id': self._country(r['country_code']), 'email': _s(r['email']),
                'phone': _s(r['phone']), 'website': _s(r['website']), 'street': _s(r['street']),
                'street2': _s(r['street2']), 'city': _s(r['city']), 'zip': _s(r['zip']),
                'function': _s(r['function']), 'customer_rank': r['customer_rank'] or 0,
                'supplier_rank': r['supplier_rank'] or 0, 'comment': _s(r['comment']),
                'active': bool(r['active']),
                'ems_category': PARTNER_CATEGORY.get((_s(r['x_category']) or '').lower()),
                'ems_is_end_client': bool(r['x_is_end_client']), 'ems_is_consultant': bool(r['x_is_consultant']),
                'ems_sector': _s(r['x_sector']), 'ems_licence_no': _s(r['x_licence_no']),
                'ems_licence_expiry': _date(r['x_licence_expiry']),
                'ems_client_payment_days': r['x_client_payment_days'] or 30,
                'ems_profile': _s(r['x_profile']),
            }
            if r['mobile'] and not vals['phone']:
                vals['phone'] = r['mobile']
            elif r['mobile'] and r['mobile'] != vals['phone']:
                vals['phone'] = '%s / %s' % (vals['phone'], r['mobile'])
            if isinstance(r['image_1920'], bytes):
                vals['image_1920'] = base64.b64encode(r['image_1920']).decode()
            partner = self._upsert('res.partner', 'res_partner', r['id'], vals, c)
            if not partner:
                continue
            if _s(r['x_contact_name']) and not partner.child_ids.filtered(lambda p: p.name == r['x_contact_name']):
                self.env['res.partner'].create({
                    'name': r['x_contact_name'], 'parent_id': partner.id, 'type': 'contact',
                    'email': _s(r['x_contact_email']), 'phone': _s(r['x_contact_phone'])})
            if _s(r['x_bank']):
                partner.comment = '%s\nBank (legacy): %s' % (partner.comment or '', r['x_bank'])

    def _m_roles(self, conn, c):
        for r in conn.execute('SELECT * FROM x_hr_role'):
            vals = {'name': r['name'], 'ems_summary': _s(r['summary']),
                    'ems_responsibilities': _s(r['responsibilities']), 'ems_qualifications': _s(r['qualifications']),
                    'active': bool(r['active'])}
            dept = _s(r['department'])
            if dept:
                vals['department_id'] = self._department(dept).id
            self._upsert('hr.job', 'x_hr_role', r['id'], vals, c)

    def _department(self, name):
        dept = self.env['hr.department'].search([('name', '=', name)], limit=1)
        return dept or self.env['hr.department'].create({'name': name})

    def _m_employees(self, conn, c):
        for r in conn.execute('SELECT * FROM hr_employee ORDER BY id'):
            vals = {
                'name': r['name'], 'ems_code': _s(r['x_code']), 'job_title': _s(r['job_title']),
                'ems_grade_id': self._ref('x_grade', r['grade_id']) or False,
                'ems_employment_type': EMPLOYMENT.get((_s(r['employment_type']) or '').lower(), 'full'),
                'work_email': _s(r['work_email']), 'mobile_phone': _s(r['mobile_phone']),
                'ems_hours_week': r['x_hours_week'] or 40.0, 'ems_plannable': bool(r['x_plannable']),
                'ems_date_start': _date(r['date_start']), 'ems_date_end': _date(r['date_end']),
                'ems_notes': _s(r['notes']), 'active': bool(r['active']),
            }
            if _s(r['department']):
                vals['department_id'] = self._department(r['department']).id
            self._upsert('hr.employee', 'hr_employee', r['id'], vals, c)
        for r in conn.execute("SELECT id, x_manager FROM hr_employee WHERE x_manager IS NOT NULL AND x_manager != ''"):
            manager = self.env['hr.employee'].search([('name', '=', r['x_manager'])], limit=1)
            emp = self.env['hr.employee'].browse(self._ref('hr_employee', r['id']))
            if manager and emp and manager != emp:
                emp.parent_id = manager

    def _m_service_items(self, conn, c):
        for r in conn.execute('SELECT * FROM x_service_item'):
            self._upsert('product.template', 'x_service_item', r['id'], {
                'name': r['name'], 'default_code': _s(r['code']), 'type': 'service', 'ems_is_service_item': True,
                'ems_discipline': _s(r['discipline']), 'list_price': r['unit_price'] or 0.0,
                'description_sale': _s(r['description']), 'active': bool(r['active'])}, c)

    def _stage(self, name):
        Stage = self.env['crm.stage']
        stage = Stage.search([('name', '=', name)], limit=1)
        return stage or Stage.create({'name': name})

    def _m_leads(self, conn, c):
        for r in conn.execute('SELECT * FROM crm_lead ORDER BY id'):
            stage = self._stage(LEAD_STAGES.get(r['stage'], 'Proposal Submitted'))
            scope = _s(r['x_scope']) or ''
            if _s(r['x_end_client']):
                scope = ('%s\nEnd client (legacy): %s' % (scope, r['x_end_client'])).strip()
            vals = {
                'name': r['name'], 'type': 'opportunity', 'partner_id': self._ref('res_partner', r['partner_id']) or False,
                'ems_number': _s(r['x_number']), 'ems_category': CATEGORY.get((_s(r['x_category']) or '').lower(), 'other'),
                'ems_project_code': _s(r['x_project_code']), 'ems_client_code': _s(r['x_client_code']),
                'contact_name': _s(r['x_contact_name']), 'email_from': _s(r['x_contact_email']),
                'phone': _s(r['x_contact_phone']), 'ems_scope': scope or False,
                'ems_discipline': _s(r['x_discipline']), 'ems_location': _s(r['x_location']),
                'stage_id': stage.id, 'ems_awarded_value': r['x_awarded_value'] or 0.0,
                'ems_rfp_date': _date(r['date_open']), 'date_deadline': _date(r['date_deadline']),
                'ems_register_code': _s(r['x_register_code']), 'ems_competitor': _s(r['x_competitor']),
                'ems_competitor_fee': r['x_competitor_fee'] or 0.0, 'ems_follow_up_date': _date(r['x_follow_up_date']),
                'ems_follow_up_method': METHODS.get((_s(r['x_follow_up_method']) or '').lower()),
                'ems_client_response': _s(r['x_client_response']), 'ems_next_follow_up': _date(r['x_next_follow_up']),
                'ems_next_follow_up_method': METHODS.get((_s(r['x_next_method']) or '').lower()),
                'ems_folder': _s(r['x_folder']), 'ems_proposal_file': _s(r['x_proposal_file']),
                'description': _s(r['description']) or ('Imported from %s' % r['x_source'] if _s(r['x_source']) else False),
                'active': True,
            }
            lead = self._upsert('crm.lead', 'crm_lead', r['id'], vals, c)
            if not lead:
                continue
            if r['stage'] in ('lost', 'regret', 'cancelled') and lead.active:
                reason = _s(r['x_lost_reason'])
                lost = False
                if reason:
                    Lost = self.env['crm.lost.reason']
                    lost = Lost.search([('name', '=', reason)], limit=1) or Lost.create({'name': reason})
                lead.action_set_lost(lost_reason_id=lost.id if lost else False)
                lead.stage_id = stage
            elif r['stage'] in ('won', 'completed') and lead.stage_id != stage:
                lead.stage_id = stage

    def _m_revisions(self, conn, c):
        for r in conn.execute('SELECT * FROM crm_lead_revision ORDER BY id'):
            lead_id = self._ref('crm_lead', r['lead_id'])
            if not lead_id:
                c['skipped'] += 1
                continue
            self._upsert('ems.lead.revision', 'crm_lead_revision', r['id'], {
                'lead_id': lead_id, 'revision': r['revision'] or 'R00', 'date': _date(r['date']) or fields.Date.today(),
                'amount': r['amount'] or 0.0, 'note': _s(r['note'])}, c)

    def _project_stage(self, name):
        Stage = self.env['project.project.stage']
        stage = Stage.search([('name', '=', name)], limit=1)
        return stage or Stage.create({'name': name, 'fold': name in ('Done', 'Cancelled')})

    def _m_projects(self, conn, c):
        for r in conn.execute('SELECT * FROM project_project ORDER BY id'):
            desc = _s(r['description']) or ''
            if _s(r['x_account_manager']):
                desc = ('%s\nAccount manager (legacy): %s' % (desc, r['x_account_manager'])).strip()
            vals = {
                'name': r['name'], 'ems_code': _s(r['x_code']), 'partner_id': self._ref('res_partner', r['partner_id']) or False,
                'ems_contract_ref': _s(r['x_contract_ref']), 'ems_contract_value': r['x_contract_value'] or 0.0,
                'ems_delivery_budget': r['x_delivery_budget'] or 0.0, 'ems_sub_budget': r['x_sub_budget'] or 0.0,
                'date_start': _date(r['date_start']), 'date': _date(r['date']),
                'description': desc or False, 'ems_authority': _s(r['x_authority']),
                'ems_authority_ref': _s(r['x_authority_ref']), 'ems_variation_value': r['x_variation_value'] or 0.0,
                'ems_client_po': _s(r['x_client_po']), 'ems_service': _s(r['x_service']),
                'ems_end_client_id': self._ref('res_partner', r['x_end_client_id']) or False,
                'ems_consultant_id': self._ref('res_partner', r['x_consultant_id']) or False,
                'active': bool(r['active']),
            }
            if _s(r['stage']):
                vals['stage_id'] = self._project_stage(r['stage']).id
            self._upsert('project.project', 'project_project', r['id'], vals, c)

    def _link_proposals_to_projects(self, conn):
        for r in conn.execute('SELECT id, x_proposal_id FROM project_project WHERE x_proposal_id IS NOT NULL'):
            project = self.env['project.project'].browse(self._ref('project_project', r['id']))
            lead = self.env['crm.lead'].browse(self._ref('crm_lead', r['x_proposal_id']))
            if project and lead:
                project.ems_proposal_id = lead
                lead.ems_project_id = project

    def _m_fee_stages(self, conn, c):
        for r in conn.execute('SELECT * FROM x_fee_stage ORDER BY id'):
            project_id = self._ref('project_project', r['project_id'])
            if not project_id:
                c['skipped'] += 1
                continue
            project = self.env['project.project'].browse(project_id)
            percent = r['percent'] or 0.0
            amount = r['amount'] or 0.0
            expected = project.ems_contract_value * percent / 100.0
            basis = 'percent' if percent and abs(expected - amount) <= 1.0 else 'fixed'
            vals = {'project_id': project_id, 'sequence': r['sequence'] or 10, 'phase': _s(r['phase']),
                    'name': r['name'] or 'Stage', 'percent': percent, 'basis': basis, 'amount': amount,
                    'progress': r['progress'] or 0.0}
            self._upsert('ems.fee.stage', 'x_fee_stage', r['id'], vals, c)

    def _m_invoices(self, conn, c):
        Move = self.env['account.move']
        journal = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)
        bank = self.env['account.journal'].search([('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id)], limit=1)
        if not journal:
            self._issue(_('No sales journal: client invoices were not imported. Configure the chart of accounts and run again.'),
                        '1_critical', 'no_journal')
            c['skipped'] = conn.execute('SELECT count(*) FROM x_client_invoice').fetchone()[0]
            return
        Tax = self.env['account.tax']
        tax5 = Tax.search([('type_tax_use', '=', 'sale'), ('amount_type', '=', 'percent'), ('amount', '=', 5.0),
                           ('company_id', '=', self.env.company.id)], limit=1)
        if not tax5:
            tax5 = Tax.create({'name': 'VAT 5%', 'type_tax_use': 'sale', 'amount_type': 'percent', 'amount': 5.0,
                               'company_id': self.env.company.id})
        for r in conn.execute('SELECT * FROM x_client_invoice ORDER BY id'):
            xml = self.env['ir.model.data'].sudo().search([
                ('module', '=', XMLID_MODULE), ('name', '=', self._xid('x_client_invoice', r['id']))], limit=1)
            if xml and Move.browse(xml.res_id).exists():
                move = Move.browse(xml.res_id)
                move.write({'ems_follow_up_date': _date(r['x_follow_up_date'])})
                c['updated'] += 1
                continue
            untaxed = r['amount_untaxed'] or 0.0
            tax = r['amount_tax'] or 0.0
            use_tax = bool(tax5 and untaxed and abs(tax - untaxed * 0.05) < 0.05)
            vals = {
                'move_type': 'out_invoice', 'journal_id': journal.id,
                'partner_id': self._ref('res_partner', r['partner_id']) or False,
                'invoice_date': _date(r['invoice_date']), 'invoice_date_due': _date(r['invoice_date_due']),
                'ref': _s(r['name']) or _s(r['ref']), 'narration': _s(r['narration']),
                'ems_project_id': self._ref('project_project', r['project_id']) or False,
                'ems_fee_stage_id': self._ref('x_fee_stage', r['stage_id']) or False,
                'ems_follow_up_date': _date(r['x_follow_up_date']),
                'ems_follow_up_method': METHODS.get((_s(r['x_follow_up_method']) or '').lower()),
                'ems_follow_up_notes': _s(r['x_follow_up_notes']), 'ems_client_response': _s(r['x_client_response']),
                'ems_next_follow_up': _date(r['x_next_follow_up']),
                'ems_next_follow_up_method': METHODS.get((_s(r['x_next_method']) or '').lower()),
                'invoice_line_ids': [(0, 0, {
                    'name': _s(r['ref']) or _s(r['name']) or 'Professional fees', 'quantity': 1,
                    'price_unit': untaxed, 'tax_ids': [(6, 0, tax5.ids)] if use_tax else [(6, 0, [])]})],
            }
            if not vals['partner_id']:
                c['skipped'] += 1
                self._issue(_('Invoice %s has no customer, so it was not migrated.') % (r['name'] or r['id']),
                            '2_high', 'invoice_no_partner', resolution=_('Enter the invoice manually once the customer is known.'))
                continue
            move = Move.create(vals)
            if r['state'] == 'posted':
                move.action_post()
                paid = r['x_amount_paid'] or 0.0
                if paid > 0.005 and bank:
                    self.env['account.payment.register'].with_context(
                        active_model='account.move', active_ids=move.ids).create({
                            'payment_date': _date(r['x_payment_date']) or _date(r['invoice_date']),
                            'amount': min(paid, move.amount_residual), 'journal_id': bank.id,
                        })._create_payments()
                if abs(move.amount_total - (r['amount_total'] or 0.0)) > 0.05:
                    self._issue(_('Invoice %s: total %.2f in Odoo differs from legacy %.2f (VAT treatment).') % (
                        r['name'], move.amount_total, r['amount_total'] or 0.0), '3_medium', 'invoice_total', move)
            self.env['ir.model.data'].sudo().create({
                'module': XMLID_MODULE, 'name': self._xid('x_client_invoice', r['id']),
                'model': 'account.move', 'res_id': move.id, 'noupdate': True})
            c['created'] += 1

    def _m_purchase_orders(self, conn, c):
        for r in conn.execute('SELECT * FROM purchase_order ORDER BY id'):
            partner_id = self._ref('res_partner', r['partner_id'])
            if not partner_id:
                c['skipped'] += 1
                continue
            product = self.env.ref('ems_register.product_subconsultancy').product_variant_id
            lines = [(0, 0, {
                'product_id': product.id, 'name': ln['name'] or 'Line', 'product_qty': ln['product_qty'] or 1.0,
                'price_unit': ln['price_unit'] or 0.0,
            }) for ln in conn.execute('SELECT * FROM purchase_order_line WHERE order_id = ? ORDER BY sequence', (r['id'],))]
            vals = {
                'partner_id': partner_id, 'ems_project_id': self._ref('project_project', r['project_id']) or False,
                'partner_ref': _s(r['partner_ref']), 'ems_quotation_ref': _s(r['x_quotation_ref']),
                'ems_quotation_date': _date(r['x_quotation_date']), 'ems_exclusions': _s(r['x_exclusions']),
                'date_order': _date(r['date_order']) or fields.Date.today(), 'origin': _s(r['origin']),
                'ems_loa_ref': _s(r['x_loa_ref']), 'ems_loa_revision': _int(r['x_loa_revision'], 0),
                'ems_loa_date': _date(r['x_loa_date']), 'ems_signed_by': _s(r['x_signed_by']),
                'ems_signed': bool(r['x_signed']), 'ems_date_start': _date(r['x_date_start']),
                'ems_duration': _int(r['x_duration'], 0), 'ems_payment_days': _int(r['x_payment_days'], 30),
                'ems_scope': _s(r['x_scope']), 'ems_deliverables': _s(r['x_deliverables']),
                'ems_document_location': _s(r['x_document_location']), 'ems_follow_up_date': _date(r['x_follow_up_date']),
                'ems_next_action': _s(r['x_next_action']), 'ems_print_count': _int(r['x_print_count'], 0),
                'ems_advance_pct': r['x_advance_pct'] or 0.0, 'ems_retention_pct': r['x_retention_pct'] or 0.0,
                'ems_retention_release': _s(r['x_retention_release']), 'ems_governing_law': _s(r['x_governing_law']),
                'ems_forum': _s(r['x_forum']), 'ems_liability_cap': _s(r['x_liability_cap']),
                'ems_insurance': _s(r['x_insurance']), 'ems_delay_damages': _s(r['x_delay_damages']),
                'ems_notice_days': _int(r['x_notice_days'], 0), 'ems_cure_days': _int(r['x_cure_days'], 0),
                'ems_restriction_months': _int(r['x_restriction_months'], 0), 'ems_review_days': _int(r['x_review_days'], 0),
                'ems_notice_email': _s(r['x_notice_email']), 'ems_special_conditions': _s(r['x_special_conditions']),
                'ems_terms': _s(r['x_terms']), 'note': _s(r['notes']),
            }
            xml = self.env['ir.model.data'].sudo().search([
                ('module', '=', XMLID_MODULE), ('name', '=', self._xid('purchase_order', r['id']))], limit=1)
            if xml and self.env['purchase.order'].browse(xml.res_id).exists():
                self.env['purchase.order'].browse(xml.res_id).write(vals)
                c['updated'] += 1
                continue
            vals['order_line'] = lines
            po = self.env['purchase.order'].create(vals)
            if not po.ems_project_id:
                po.ems_overhead = True
            for ms in conn.execute('SELECT * FROM purchase_payment_milestone WHERE order_id = ? ORDER BY sequence', (r['id'],)):
                self.env['ems.po.milestone'].create({
                    'order_id': po.id, 'name': ms['name'] or 'Milestone', 'percent': ms['percent'] or 0.0})
            if r['state'] in ('purchase', 'done'):
                po.button_confirm()
            self.env['ir.model.data'].sudo().create({
                'module': XMLID_MODULE, 'name': self._xid('purchase_order', r['id']),
                'model': 'purchase.order', 'res_id': po.id, 'noupdate': True})
            c['created'] += 1

    def _m_services(self, conn, c):
        for r in conn.execute('SELECT * FROM x_project_service ORDER BY id'):
            project_id = self._ref('project_project', r['project_id'])
            if not project_id:
                c['skipped'] += 1
                continue
            self._upsert('ems.project.service', 'x_project_service', r['id'], {
                'project_id': project_id, 'code': r['x_code'] or str(r['id']), 'name': r['name'],
                'discipline': _s(r['discipline']), 'fee': r['fee'] or 0.0, 'budget_hours': r['budget_hours'] or 0.0,
                'state': r['state'] if r['state'] in ('planned', 'active', 'on_hold', 'done', 'cancelled') else 'active',
                'date_start': _date(r['date_start']), 'date_end': _date(r['date_end']), 'notes': _s(r['notes']),
            }, c)

    def _m_milestones(self, conn, c):
        for r in conn.execute('SELECT * FROM x_project_milestone ORDER BY id'):
            project_id = self._ref('project_project', r['project_id'])
            if not project_id:
                c['skipped'] += 1
                continue
            self._upsert('project.milestone', 'x_project_milestone', r['id'], {
                'name': r['name'], 'project_id': project_id,
                'ems_service_id': self._ref('x_project_service', r['service_id']) or False,
                'ems_date_start': _date(r['date_start']), 'deadline': _date(r['date_deadline']),
                'ems_budget_hours': r['budget_hours'] or 0.0,
                'ems_state': r['state'] if r['state'] in ('todo', 'in_progress', 'review', 'done', 'blocked') else 'todo',
                'ems_progress': r['progress'] or 0.0, 'ems_description': _s(r['description']),
                'is_reached': r['state'] == 'done',
            }, c)

    def _m_allocations(self, conn, c):
        for r in conn.execute('SELECT * FROM x_allocation ORDER BY id'):
            emp = self._ref('hr_employee', r['employee_id'])
            project = self._ref('project_project', r['project_id'])
            if not (emp and project):
                c['skipped'] += 1
                continue
            self._upsert('ems.allocation', 'x_allocation', r['id'], {
                'name': r['name'] or 'Allocation', 'employee_id': emp, 'project_id': project,
                'service_id': self._ref('x_project_service', r['service_id']) or False,
                'milestone_id': self._ref('x_project_milestone', r['milestone_id']) or False,
                'date_from': _date(r['date_from']), 'date_to': _date(r['date_to']),
                'hours_per_day': r['hours_per_day'] or 8.0, 'tentative': bool(r['x_tentative']),
            }, c)

    def _m_offers(self, conn, c):
        for r in conn.execute('SELECT * FROM x_offer ORDER BY id'):
            state = r['state'] if r['state'] in ('draft', 'sent', 'accepted', 'declined', 'withdrawn', 'expired') else 'draft'
            vals = {
                'candidate': r['candidate'], 'candidate_email': _s(r['email']),
                'job_id': self._ref('x_hr_role', r['role_id']) or False,
                'grade_id': self._ref('x_grade', r['grade_id']) or False,
                'offer_date': _date(r['date_offer']), 'start_date': _date(r['date_start']),
                'salary_basic': r['basic'] or 0.0, 'salary_housing': r['housing'] or 0.0,
                'salary_transport': r['transport'] or 0.0, 'salary_other': r['other'] or 0.0,
                'probation_months': r['probation_months'] or 0, 'air_ticket': _s(r['air_ticket']),
                'benefits': _s(r['benefits_text']), 'job_description': _s(r['job_duties']),
                'letter_body': _s(r['special_terms']), 'notes': _s(r['notes']),
                'employee_id': self._ref('hr_employee', r['employee_id']) or False,
            }
            offer = self._upsert('ems.offer', 'x_offer', r['id'], vals, c)
            if offer:
                offer.state = state

    def _m_attachments(self, conn, c):
        for r in conn.execute('SELECT * FROM ir_attachment ORDER BY id'):
            model = TABLE_MODEL.get(r['res_model'])
            res_id = self._ref(r['res_model'], r['res_id'])
            if not (model and res_id):
                c['skipped'] += 1
                continue
            data = r['datas']
            vals = {
                'name': r['name'], 'filename': r['name'], 'res_model': model, 'res_id': res_id,
                'category': DOC_CATEGORY.get((_s(r['x_category']) or 'other').lower(), 'other'),
                'note': _s(r['description']) or ('Legacy path: %s' % r['store_fname'] if _s(r['store_fname']) else False),
            }
            if isinstance(data, bytes):
                vals['file'] = base64.b64encode(data).decode()
            elif isinstance(data, str) and data:
                vals['file'] = data
            else:
                self._issue(_('Attachment "%s" has no file content in the backup (legacy path %s): copy it manually.') % (
                    r['name'], r['store_fname']), '4_low', 'attachment_missing')
            self._upsert('ems.document', 'ir_attachment', r['id'], vals, c)

    def _m_chatter(self, conn, c):
        for r in conn.execute('SELECT * FROM mail_message ORDER BY id'):
            model = CHATTER_MODELS.get(r['model'])
            res_id = self._ref(r['model'], r['res_id'])
            if not (model and res_id):
                c['skipped'] += 1
                continue
            xml = self.env['ir.model.data'].sudo().search([
                ('module', '=', XMLID_MODULE), ('name', '=', self._xid('mail_message', r['id']))], limit=1)
            if xml:
                c['skipped'] += 1
                continue
            record = self.env[model].browse(res_id)
            if not record.exists() or not hasattr(record, 'message_post'):
                c['skipped'] += 1
                continue
            body = '<p><i>%s, %s (legacy)</i><br/>%s</p>' % (
                r['author'] or 'System', (r['date'] or '')[:16], (r['body'] or '').replace('<', '&lt;'))
            msg = record.message_post(body=body, message_type='comment', subtype_xmlid='mail.mt_note',
                                      date=fields.Datetime.to_datetime(r['date']) if r['date'] else False)
            self.env['ir.model.data'].sudo().create({
                'module': XMLID_MODULE, 'name': self._xid('mail_message', r['id']),
                'model': 'mail.message', 'res_id': msg.id, 'noupdate': True})
            c['created'] += 1

    # ------------------------------------------------------------------ data quality
    def _detect_issues(self, conn):
        Lead = self.env['crm.lead']
        Project = self.env['project.project']
        # 1. projects not linked to a proposal
        for r in conn.execute("SELECT id, name FROM project_project WHERE x_proposal_id IS NULL AND active=1"):
            project = Project.browse(self._ref('project_project', r['id']))
            if project:
                self._issue(_('Project "%s" is not linked to a proposal.') % r['name'], '3_medium', 'project_no_proposal',
                            project, resolution=_('Link the project to its proposal (Link Project on the proposal).'))
        # 2. won proposals with zero awarded value, and without a project
        for r in conn.execute("SELECT id, name, x_number FROM crm_lead WHERE stage IN ('won','completed') AND COALESCE(x_awarded_value,0)=0"):
            lead = Lead.browse(self._ref('crm_lead', r['id']))
            if lead:
                self._issue(_('Won proposal %s has awarded value 0.') % (r['x_number'] or r['name']), '2_high',
                            'won_zero_award', lead, resolution=_('Enter the awarded value from the signed PO.'))
        # 3. duplicate proposals (same normalised name)
        seen = defaultdict(list)
        for r in conn.execute('SELECT id, name, x_number FROM crm_lead'):
            seen[re.sub(r'[^a-z0-9]', '', (r['name'] or '').lower())].append(r)
        for rows in seen.values():
            if len(rows) > 1:
                lead = Lead.browse(self._ref('crm_lead', rows[0]['id']))
                self._issue(_('Possible duplicate proposals: %s') % ', '.join(
                    str(x['x_number'] or x['id']) for x in rows), '3_medium', 'duplicate_lead', lead,
                    resolution=_('Merge or archive the duplicates.'))
        # 4. fee stages that do not add to 100 % of the contract
        for r in conn.execute("""SELECT project_id, SUM(percent) AS pct FROM x_fee_stage
                                 WHERE percent > 0 GROUP BY project_id HAVING ABS(SUM(percent) - 100) > 0.5"""):
            project = Project.browse(self._ref('project_project', r['project_id']))
            if project:
                self._issue(_('Fee stages of %(p)s add up to %(v).1f%%, not 100%%.', p=project.display_name, v=r['pct']),
                            '3_medium', 'fee_not_100', project, resolution=_('Correct the fee stages.'))
        # 5. unpaid invoices
        for r in conn.execute("""SELECT project_id, COUNT(*) AS n, SUM(amount_untaxed - COALESCE(x_amount_paid,0)) AS open
                                 FROM x_client_invoice WHERE payment_state != 'paid' GROUP BY project_id"""):
            project = Project.browse(self._ref('project_project', r['project_id']))
            if project and r['open'] and r['open'] > 1:
                self._issue(_('%(n)s unpaid invoice(s) on %(p)s, about %(v).0f ex VAT.', n=r['n'], p=project.display_name,
                              v=r['open']), '4_low', 'unpaid_invoices', project)
        # 6. employees without grade or planning capacity
        for r in conn.execute('SELECT id, name FROM hr_employee WHERE grade_id IS NULL AND active=1'):
            emp = self.env['hr.employee'].browse(self._ref('hr_employee', r['id']))
            if emp:
                self._issue(_('Employee %s has no grade, so no cost rate can apply.') % r['name'], '3_medium',
                            'employee_no_grade', emp)
        self._issue(_('Internal cost rates, charge-out rates, bank and MOL details live in the encrypted exe vault and '
                      'were NOT migrated. The Rates Manager must enter them in Odoo.'), '1_critical', 'rates_vault',
                    resolution=_('Enter grade and employee cost rates under EMS People > Grades.'))
        # 7. closed projects with open work: done but unpaid
        for r in conn.execute("""SELECT p.id, p.name FROM project_project p WHERE p.stage='Done' AND EXISTS
                                 (SELECT 1 FROM x_client_invoice i WHERE i.project_id=p.id AND i.payment_state!='paid')"""):
            project = Project.browse(self._ref('project_project', r['id']))
            if project:
                self._issue(_('Project "%s" is Done but still has unpaid invoices.') % r['name'], '3_medium',
                            'done_unpaid', project)
        # 8. proposal dates: RFP after submission or award
        for r in conn.execute("""SELECT id, name, x_number FROM crm_lead WHERE date_open IS NOT NULL
                                 AND x_date_submitted IS NOT NULL AND date_open > x_date_submitted"""):
            lead = Lead.browse(self._ref('crm_lead', r['id']))
            if lead:
                self._issue(_('Proposal %s: RFP date is after the submission date.') % (r['x_number'] or r['name']),
                            '2_high', 'rfp_after_submission', lead, resolution=_('Validate the actual RFP date.'))

    def action_view_issues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Data Issues'), 'res_model': 'ems.data.issue',
            'view_mode': 'list,form', 'domain': [('run_id', '=', self.id)],
        }


class EmsMigrationSummary(models.Model):
    _name = 'ems.migration.summary'
    _description = 'EMS Migration Summary Line'
    _order = 'id'

    run_id = fields.Many2one('ems.migration.run', required=True, ondelete='cascade')
    table = fields.Char('Legacy Table')
    created = fields.Integer()
    updated = fields.Integer()
    skipped = fields.Integer()
    failed = fields.Integer()
