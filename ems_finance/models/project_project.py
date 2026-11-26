from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Award baseline chain: Client > Opportunity > Revision > Sales Order > Project > Analytic Account
    ems_sale_order_id = fields.Many2one('sale.order', 'Award (Sales Order)', copy=False, tracking=True, index=True)
    ems_baseline_value = fields.Monetary('Baseline Value (ex VAT)', currency_field='ems_currency_id', copy=False,
                                         readonly=True)
    ems_baseline_date = fields.Date('Baseline Date', copy=False, readonly=True)
    ems_baseline_hours = fields.Float('Baseline Hours', copy=False, readonly=True)
    ems_ntp_date = fields.Date('NTP Date')
    ems_mobilised = fields.Boolean('Mobilised', tracking=True,
                                   help='Resource plan and budget reviewed; delivery can start.')
    ems_excluded_amount = fields.Monetary(
        'Proposal Items Not Awarded', currency_field='ems_currency_id', compute='_compute_ems_excluded')
    ems_closed = fields.Boolean('Closed', copy=False, readonly=True, tracking=True)
    ems_closed_date = fields.Date(copy=False, readonly=True)

    # Variations
    ems_variation_ids = fields.One2many('ems.variation', 'project_id', string='Variation Register')
    ems_variation_count = fields.Integer(compute='_compute_ems_variation')
    ems_variation_pending = fields.Monetary('Variations Awaiting Approval', currency_field='ems_currency_id',
                                            compute='_compute_ems_variation')

    # WBS / timesheets
    ems_wbs_count = fields.Integer('WBS Stages', compute='_compute_ems_wbs')
    ems_hours_budget = fields.Float('Budget Hours', compute='_compute_ems_hours')
    ems_hours_actual = fields.Float('Approved Hours', compute='_compute_ems_hours')
    ems_hours_unapproved = fields.Float('Unapproved Hours', compute='_compute_ems_hours')

    # Costs: commitments are never double counted with bills
    ems_vendor_billed = fields.Monetary('Vendor Bills Posted (ex VAT)', currency_field='ems_currency_id',
                                        compute='_compute_ems_vendor_costs')
    ems_open_commitment = fields.Monetary('Open Commitments (PO not yet billed)', currency_field='ems_currency_id',
                                          compute='_compute_ems_vendor_costs')

    # Economics (profit snapshot, live). Labour based figures follow the cost-rate restriction.
    ems_planned_labour = fields.Monetary('Planned Labour Cost', currency_field='ems_currency_id',
                                         compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_actual_labour = fields.Monetary('Actual Labour Cost', currency_field='ems_currency_id',
                                        compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_etc_labour = fields.Monetary('Estimate to Complete (labour)', currency_field='ems_currency_id',
                                     compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_eac = fields.Monetary('Estimate at Completion', currency_field='ems_currency_id',
                              compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_forecast_margin = fields.Monetary('Forecast Margin', currency_field='ems_currency_id',
                                          compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_forecast_margin_pct = fields.Float('Forecast Margin %', compute='_compute_ems_economics',
                                           groups='ems_base.group_ems_rates')
    ems_realised_margin = fields.Monetary('Realised Margin', currency_field='ems_currency_id',
                                          compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_overhead_amount = fields.Monetary('Overhead Allocation', currency_field='ems_currency_id',
                                          compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_margin_after_overhead = fields.Monetary('Forecast Margin after Overhead', currency_field='ems_currency_id',
                                                compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_cost_variance = fields.Monetary('Cost Variance vs Budget', currency_field='ems_currency_id',
                                        compute='_compute_ems_economics', groups='ems_base.group_ems_rates')
    ems_collected = fields.Monetary('Cash Collected (incl. VAT)', currency_field='ems_currency_id',
                                    compute='_compute_ems_economics')
    ems_profit_snapshot_ids = fields.One2many('ems.profit.snapshot', 'project_id', string='Profit Snapshots')

    # ------------------------------------------------------------------
    @api.depends('ems_sale_order_id.order_line.ems_excluded_price')
    def _compute_ems_excluded(self):
        for project in self:
            project.ems_excluded_amount = sum(project.ems_sale_order_id.order_line.mapped('ems_excluded_price'))

    @api.depends('ems_variation_ids.state', 'ems_variation_ids.amount')
    def _compute_ems_variation(self):
        for project in self:
            project.ems_variation_count = len(project.ems_variation_ids)
            pending = project.ems_variation_ids.filtered(lambda v: v.state in ('draft', 'submitted'))
            project.ems_variation_pending = sum(pending.mapped('amount'))

    def _compute_ems_wbs(self):
        data = self.env['project.task'].sudo()._read_group(
            [('project_id', 'in', self.ids), ('ems_wbs_code', '!=', False)], ['project_id'], ['__count'])
        counts = {p.id: c for p, c in data}
        for project in self:
            project.ems_wbs_count = counts.get(project.id, 0)

    def _compute_ems_hours(self):
        Line = self.env['account.analytic.line'].sudo()
        for project in self:
            lines = Line.search([('project_id', '=', project.id)])
            project.ems_hours_budget = sum(project.ems_service_ids.mapped('budget_hours')) or project.ems_baseline_hours
            project.ems_hours_actual = sum(lines.filtered(lambda l: l.ems_state == 'approved').mapped('unit_amount'))
            project.ems_hours_unapproved = sum(lines.filtered(lambda l: l.ems_state != 'approved').mapped('unit_amount'))

    def _ems_vendor_figures(self):
        """Return {project_id: (billed, open_commitment)} without double counting PO and bill."""
        Line = self.env['account.move.line'].sudo()
        res = {}
        for project in self:
            pos = project.ems_po_ids.sudo().filtered(lambda p: p.state in ('purchase', 'done'))
            lines = Line.search([
                ('move_id.state', '=', 'posted'), ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
                ('display_type', '=', 'product'),
                '|', ('purchase_line_id.order_id.ems_project_id', '=', project.id),
                '&', ('purchase_line_id', '=', False), ('move_id.ems_project_id', '=', project.id)])
            billed = 0.0
            billed_po = {}
            for line in lines:
                sign = -1.0 if line.move_id.move_type == 'in_refund' else 1.0
                amount = sign * line.price_subtotal
                billed += amount
                order = line.purchase_line_id.order_id
                if order:
                    billed_po[order.id] = billed_po.get(order.id, 0.0) + amount
            open_commit = sum(max(po.amount_untaxed - billed_po.get(po.id, 0.0), 0.0) for po in pos)
            res[project.id] = (billed, open_commit)
        return res

    def _compute_ems_vendor_costs(self):
        figures = self._ems_vendor_figures()
        for project in self:
            project.ems_vendor_billed, project.ems_open_commitment = figures.get(project.id, (0.0, 0.0))

    def _ems_economics(self):
        """Profit snapshot numbers for each project (ex VAT unless stated)."""
        today = fields.Date.context_today(self)
        overhead_pct = float(self.env['ir.config_parameter'].sudo().get_str('ems.overhead_pct') or 0.0)
        vendor = self._ems_vendor_figures()
        res = {}
        for project in self:
            sp = project.sudo()
            invoices = self.env['account.move'].sudo().search([
                ('ems_project_id', '=', sp.id), ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted')])
            invoiced = collected = receivable = 0.0
            for inv in invoices:
                sign = -1.0 if inv.move_type == 'out_refund' else 1.0
                invoiced += sign * inv.amount_untaxed
                collected += sign * (inv.amount_total - inv.amount_residual)
                receivable += sign * inv.amount_residual
            allocs = self.env['ems.allocation'].sudo().search([('project_id', '=', sp.id)])
            planned = sum(allocs.mapped('cost'))
            etc = 0.0
            for alloc in allocs:
                if alloc.date_to >= today:
                    days = alloc._ems_count_days(max(today, alloc.date_from), alloc.date_to)
                    etc += days * alloc.hours_per_day * alloc.employee_id._ems_cost_per_hour()
            lines = self.env['account.analytic.line'].sudo().search([
                ('project_id', '=', sp.id), ('ems_state', '=', 'approved')])
            actual_labour = sum(lines.mapped('ems_cost_amount'))
            billed, open_commit = vendor.get(sp.id, (0.0, 0.0))
            actual_direct = actual_labour + billed
            eac = actual_direct + etc + open_commit
            contracted = sp.ems_total_value
            forecast = contracted - eac
            overhead = contracted * overhead_pct / 100.0
            budget = sp.ems_delivery_budget
            res[sp.id] = {
                'contracted': contracted, 'baseline': sp.ems_contract_value,
                'variations': sp.ems_variation_value, 'invoiced': invoiced, 'collected': collected,
                'receivable': receivable, 'planned_labour': planned, 'actual_labour': actual_labour,
                'vendor_billed': billed, 'open_commitment': open_commit, 'actual_direct': actual_direct,
                'etc_labour': etc, 'eac': eac, 'forecast_margin': forecast,
                'forecast_margin_pct': forecast / contracted * 100.0 if contracted else 0.0,
                'realised_margin': invoiced - actual_direct, 'overhead': overhead,
                'margin_after_overhead': forecast - overhead,
                'cost_variance': (eac - budget) if budget else 0.0,
                'hours_budget': sp.ems_hours_budget, 'hours_actual': sp.ems_hours_actual,
            }
        return res

    def _compute_ems_economics(self):
        figures = self._ems_economics()
        for project in self:
            f = figures[project.id]
            project.ems_planned_labour = f['planned_labour']
            project.ems_actual_labour = f['actual_labour']
            project.ems_etc_labour = f['etc_labour']
            project.ems_eac = f['eac']
            project.ems_forecast_margin = f['forecast_margin']
            project.ems_forecast_margin_pct = f['forecast_margin_pct']
            project.ems_realised_margin = f['realised_margin']
            project.ems_overhead_amount = f['overhead']
            project.ems_margin_after_overhead = f['margin_after_overhead']
            project.ems_cost_variance = f['cost_variance']
            project.ems_collected = f['collected']

    # ------------------------------------------------------------------
    def _ems_ensure_analytic_account(self):
        plan = self.env.ref('analytic.analytic_plan_projects', raise_if_not_found=False)
        for project in self:
            if not project.account_id:
                project.account_id = self.env['account.analytic.account'].create({
                    'name': '%s %s' % (project.ems_code or '', project.name),
                    'plan_id': plan.id if plan else self.env['account.analytic.plan']._get_default().id,
                    'partner_id': project.partner_id.id,
                    'company_id': project.company_id.id or False,
                })

    def action_ems_apply_wbs(self):
        """Create the P0-P7 delivery stages as tasks (idempotent)."""
        Task = self.env['project.task']
        for project in self:
            existing = set(Task.search([('project_id', '=', project.id), ('ems_wbs_code', '!=', False)]).mapped('ems_wbs_code'))
            hours = project.ems_hours_budget
            for tmpl in self.env['ems.wbs.template'].search([]):
                if tmpl.code in existing:
                    continue
                Task.create({
                    'name': '%s - %s' % (tmpl.code, tmpl.name),
                    'project_id': project.id,
                    'ems_wbs_code': tmpl.code,
                    'ems_gate': tmpl.gate,
                    'allocated_hours': hours * tmpl.budget_pct / 100.0 if hours else 0.0,
                })
        return True

    def action_view_ems_wbs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('WBS P0-P7'), 'res_model': 'project.task',
            'view_mode': 'kanban,list,form', 'domain': [('project_id', '=', self.id), ('ems_wbs_code', '!=', False)],
            'context': {'default_project_id': self.id},
        }

    def action_view_ems_variations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Variations'), 'res_model': 'ems.variation',
            'view_mode': 'list,form', 'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_ems_timesheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Timesheets'), 'res_model': 'account.analytic.line',
            'view_mode': 'list,pivot,form', 'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_ems_snapshot(self):
        self.env['ems.profit.snapshot']._take(self)
        return self.action_view_ems_snapshots()

    def action_view_ems_snapshots(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Profit Snapshots'), 'res_model': 'ems.profit.snapshot',
            'view_mode': 'list,graph,pivot', 'domain': [('project_id', '=', self.id)],
        }

    def action_view_ems_sale_order(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': self.ems_sale_order_id.id,
                'view_mode': 'form'}

    def _ems_close_blockers(self):
        self.ensure_one()
        blockers = []
        open_pos = self.ems_po_ids.filtered(lambda p: p.state in ('draft', 'sent', 'to approve'))
        if open_pos:
            blockers.append(_('%d purchase order(s) are still not confirmed or cancelled.', len(open_pos)))
        if self.ems_open_commitment > 0.005:
            blockers.append(_('Open vendor commitments of %.2f are not yet billed.', self.ems_open_commitment))
        unbilled = self.ems_total_value - self.ems_invoiced
        if unbilled > 0.005:
            blockers.append(_('%.2f of the contract value is not yet invoiced (unbilled WIP).', unbilled))
        if self.ems_outstanding > 0.005:
            blockers.append(_('%.2f of invoices is still outstanding (AR).', self.ems_outstanding))
        if self.ems_hours_unapproved > 0.005:
            blockers.append(_('%.1f timesheet hours are not approved.', self.ems_hours_unapproved))
        open_tasks = self.env['project.task'].search_count([
            ('project_id', '=', self.id), ('ems_wbs_code', '!=', False), ('is_closed', '=', False)])
        if open_tasks:
            blockers.append(_('%d WBS stage(s) are not closed.', open_tasks))
        return blockers

    def action_ems_close(self):
        """Close needs PM + Finance + management: technical and financial issues are reviewed."""
        for project in self:
            self.env['ems.approval.rule'].check('closure', project, project.ems_total_value)
            blockers = project._ems_close_blockers()
            if blockers and not self.env.context.get('ems_force_close'):
                raise UserError(_('Cannot close %(project)s yet:\n- %(blockers)s',
                                  project=project.display_name, blockers='\n- '.join(blockers)))
            project.write({'ems_closed': True, 'ems_closed_date': fields.Date.context_today(project)})
            project.message_post(body=_('Project closed. Open items at closure: %s',
                                        '; '.join(blockers) or _('none')))

    def action_ems_reopen(self):
        self.write({'ems_closed': False, 'ems_closed_date': False})

    @api.model
    def _cron_ems_profit_snapshot(self):
        self.env['ems.profit.snapshot']._take(self.search([('ems_closed', '=', False), ('ems_total_value', '>', 0)]))
