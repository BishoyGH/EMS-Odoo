from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

KIND_GROUPS = {
    'register': 'ems_base.group_ems_user', 'payments': 'ems_base.group_ems_user',
    'proposals': 'ems_base.group_ems_user', 'portfolio': 'ems_base.group_ems_user',
    'resource': 'ems_base.group_ems_user', 'economics': 'ems_base.group_ems_rates',
    'finance': 'ems_base.group_ems_manager', 'audit': 'ems_base.group_ems_admin',
}


class EmsDashboard(models.AbstractModel):
    """Data provider for the EMS OWL dashboards. Each kind returns tiles and bar charts."""
    _name = 'ems.dashboard'
    _description = 'EMS Dashboard Data'

    # ------------------------------------------------------------------ helpers
    @api.model
    def _act(self, name, model, domain=None, views='list,form', context=None):
        return {
            'type': 'ir.actions.act_window', 'name': name, 'res_model': model,
            'views': [[False, v] for v in views.split(',')], 'domain': domain or [],
            'context': context or {},
        }

    @api.model
    def _tile(self, label, value, fmt='int', sub=False, tone='primary', action=False):
        return {'label': label, 'value': value, 'fmt': fmt, 'sub': sub, 'tone': tone, 'action': action}

    @api.model
    def _bars(self, title, items, fmt='money'):
        top = max([abs(i['value']) for i in items] or [1]) or 1
        for item in items:
            item['pct'] = abs(item['value']) / top * 100.0
        return {'title': title, 'fmt': fmt, 'items': items}

    @api.model
    def get_dashboard(self, kind):
        group = KIND_GROUPS.get(kind)
        if not group:
            raise AccessError(_('Unknown dashboard.'))
        if not (self.env.is_superuser() or self.env.user.has_group(group)):
            raise AccessError(_('You are not allowed to open this dashboard.'))
        titles = {
            'register': _('Register overview'), 'payments': _('Payments'), 'proposals': _('CRM funnel and proposals'),
            'portfolio': _('Portfolio'), 'resource': _('Resources'), 'economics': _('Project economics'),
            'finance': _('Finance'), 'audit': _('Audit and controls'),
        }
        data = getattr(self, '_dash_%s' % kind)()
        currency = self.env.company.currency_id
        data.update({
            'kind': kind, 'title': titles[kind],
            'currency': {'symbol': currency.symbol, 'name': currency.name, 'position': currency.position,
                         'decimals': 0},
            'updated': fields.Datetime.to_string(fields.Datetime.now()),
        })
        return data

    @api.model
    def _sum(self, model, domain, field):
        groups = self.env[model].sudo()._read_group(domain, [], ['%s:sum' % field])
        return (groups[0][0] or 0.0) if groups else 0.0

    # ------------------------------------------------------------------ register overview
    @api.model
    def _dash_register(self):
        env = self.env
        today = fields.Date.context_today(self)
        Project = env['project.project']
        PO = env['purchase.order']
        active = [('ems_closed', '=', False), ('ems_total_value', '>', 0)]
        projects = Project.sudo().search(active)
        confirmed = PO.sudo().search([('state', 'in', ('purchase', 'done'))])
        open_commit = sum(confirmed.mapped('ems_open_amount'))
        alerts = projects.filtered(lambda p: p.ems_sub_budget and p.ems_committed > 0.9 * p.ems_sub_budget)
        bills = env['account.move'].sudo().search([('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
                                                    ('payment_state', 'in', ('not_paid', 'partial'))])
        follow = PO.sudo().search([('ems_follow_up_date', '!=', False), ('ems_follow_up_date', '<=', today),
                                    ('state', 'in', ('draft', 'sent', 'purchase'))])
        tiles = [
            self._tile(_('Active projects'), len(projects), 'int', _('Contract value %s') % '{:,.0f}'.format(
                sum(projects.mapped('ems_total_value'))), 'primary',
                       self._act(_('Active projects'), 'project.project', active)),
            self._tile(_('Contract value'), sum(projects.mapped('ems_total_value')), 'money',
                       _('incl. approved variations, ex VAT'), 'primary'),
            self._tile(_('POs / LOAs awaiting signature'), PO.sudo().search_count([('state', 'in', ('draft', 'sent'))]),
                       'int', _('drafts and issued LOAs'), 'warning',
                       self._act(_('POs awaiting signature'), 'purchase.order', [('state', 'in', ('draft', 'sent'))])),
            self._tile(_('Confirmed POs'), len(confirmed), 'int', _('open commitment %s') % '{:,.0f}'.format(open_commit),
                       'success', self._act(_('Confirmed POs'), 'purchase.order', [('state', 'in', ('purchase', 'done'))])),
            self._tile(_('Open commitments'), open_commit, 'money', _('PO value not yet billed'), 'primary'),
            self._tile(_('Vendor bills to pay'), len(bills), 'int', _('outstanding %s') % '{:,.0f}'.format(
                sum(bills.mapped('amount_residual'))), 'warning',
                       self._act(_('Vendor bills to pay'), 'account.move', [('id', 'in', bills.ids)])),
            self._tile(_('Sub-budget alerts'), len(alerts), 'int', _('above 90% of the sub-consultant budget'),
                       'danger' if alerts else 'muted', self._act(_('Sub-budget alerts'), 'project.project',
                                                                  [('id', 'in', alerts.ids)])),
            self._tile(_('PO follow-ups due'), len(follow), 'int', _('on or before today'),
                       'danger' if follow else 'muted', self._act(_('PO follow-ups due'), 'purchase.order',
                                                                  [('id', 'in', follow.ids)])),
            self._tile(_('Office overhead POs'), PO.sudo().search_count([('ems_overhead', '=', True)]), 'int',
                       _('never charged to a project'), 'muted',
                       self._act(_('Office overhead'), 'purchase.order', [('ems_overhead', '=', True)])),
        ]
        stage_groups = Project.sudo()._read_group(active, ['stage_id'], ['__count', 'ems_total_value:sum'])
        top_clients = Project.sudo()._read_group(active, ['partner_id'], ['ems_total_value:sum'],
                                                 order='ems_total_value:sum desc', limit=8)
        return {
            'sections': [{'title': _('At a glance'), 'tiles': tiles}],
            'charts': [
                self._bars(_('Contract value by project stage'), [
                    {'label': s.name or _('No stage'), 'value': v} for s, c, v in stage_groups]),
                self._bars(_('Top clients by contract value'), [
                    {'label': p.name or _('Unknown'), 'value': v} for p, v in top_clients]),
            ],
        }

    # ------------------------------------------------------------------ payments
    @api.model
    def _dash_payments(self):
        today = fields.Date.context_today(self)
        Move = self.env['account.move'].sudo()
        base = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]
        year_start = today.replace(month=1, day=1)
        invoiced = self._sum('account.move', base + [('invoice_date', '>=', year_start)], 'amount_untaxed')
        open_dom = base + [('payment_state', 'in', ('not_paid', 'partial'))]
        outstanding = self._sum('account.move', open_dom, 'amount_residual')
        overdue_dom = open_dom + [('invoice_date_due', '<', today)]
        overdue = Move.search(overdue_dom)
        stages = self.env['ems.fee.stage'].sudo().search([('eligible', '=', True)]).filtered(lambda s: s.state == 'todo')
        waiting = self.env['ems.fee.stage'].sudo().search([('eligible', '=', False)])
        waiting = waiting.filtered(lambda s: s.state == 'todo')
        due_follow = Move.search(open_dom + [('ems_next_follow_up', '!=', False), ('ems_next_follow_up', '<=', today)])
        month_start = today.replace(day=1)
        collected = self._sum('account.payment', [('payment_type', '=', 'inbound'), ('state', 'in', ('paid', 'in_process')),
                                                  ('date', '>=', month_start)], 'amount')
        tiles = [
            self._tile(_('Invoiced this year'), invoiced, 'money', _('ex VAT'), 'primary',
                       self._act(_('Invoices this year'), 'account.move', base + [('invoice_date', '>=', year_start)])),
            self._tile(_('Outstanding'), outstanding, 'money', _('incl. VAT, unpaid'), 'warning',
                       self._act(_('Outstanding invoices'), 'account.move', open_dom)),
            self._tile(_('Overdue invoices'), len(overdue), 'int', _('%s overdue') % '{:,.0f}'.format(
                sum(overdue.mapped('amount_residual'))), 'danger' if overdue else 'success',
                       self._act(_('Overdue invoices'), 'account.move', overdue_dom)),
            self._tile(_('Collected this month'), collected, 'money', _('customer receipts'), 'success'),
            self._tile(_('Ready to invoice'), len(stages), 'int', _('fee stages with evidence ticked'),
                       'primary' if stages else 'muted', self._act(_('Ready to invoice'), 'ems.fee.stage',
                                                                   [('id', 'in', stages.ids)])),
            self._tile(_('Waiting for evidence'), len(waiting), 'int', _('fee stages not yet released'), 'muted',
                       self._act(_('Waiting for evidence'), 'ems.fee.stage', [('id', 'in', waiting.ids)])),
            self._tile(_('Follow-ups due'), len(due_follow), 'int', _('next follow-up on or before today'),
                       'danger' if due_follow else 'muted', self._act(_('Follow-ups due'), 'account.move',
                                                                      [('id', 'in', due_follow.ids)])),
        ]
        aging = self.env['ems.ar.aging'].sudo()._read_group([], ['bucket'], ['residual:sum'])
        labels = dict(self.env['ems.ar.aging']._fields['bucket'].selection)
        order = ['0_current', '1_30', '31_60', '61_90', '90_plus']
        by_bucket = {b: v for b, v in aging}
        top = self.env['ems.ar.aging'].sudo()._read_group([('days_overdue', '>', 0)], ['partner_id'], ['residual:sum'],
                                                          order='residual:sum desc', limit=6)
        return {
            'sections': [{'title': _('Collections'), 'tiles': tiles}],
            'charts': [
                self._bars(_('AR aging (outstanding)'), [
                    {'label': labels[b], 'value': by_bucket.get(b, 0.0)} for b in order]),
                self._bars(_('Top overdue customers'), [{'label': p.name, 'value': v} for p, v in top]),
            ],
        }

    # ------------------------------------------------------------------ CRM funnel
    @api.model
    def _dash_proposals(self):
        today = fields.Date.context_today(self)
        Lead = self.env['crm.lead'].sudo()
        opp = [('type', '=', 'opportunity')]
        open_dom = opp + [('stage_id.is_won', '=', False), ('active', '=', True)]
        leads = Lead.search(open_dom)
        pipeline = sum(leads.mapped('expected_revenue'))
        weighted = sum(l.expected_revenue * l.probability / 100.0 for l in leads)
        year_start = today.replace(month=1, day=1)
        won = Lead.search(opp + [('stage_id.is_won', '=', True), ('date_closed', '>=', year_start)])
        lost = Lead.with_context(active_test=False).search_count(opp + [('active', '=', False), ('probability', '=', 0),
                                                                         ('date_closed', '>=', year_start)])
        win_rate = len(won) / (len(won) + lost) * 100.0 if (len(won) + lost) else 0.0
        ages = [(today - fields.Datetime.to_datetime(l.create_date).date()).days for l in leads]
        overdue = Lead.search(open_dom + [('ems_overdue', '=', True)])
        undecided = Lead.search(open_dom + [('ems_bid_decision', '=', 'pending')])
        tiles = [
            self._tile(_('Open proposals'), len(leads), 'int', _('pipeline %s') % '{:,.0f}'.format(pipeline), 'primary',
                       self._act(_('Open proposals'), 'crm.lead', open_dom)),
            self._tile(_('Weighted pipeline'), weighted, 'money', _('value x probability'), 'primary'),
            self._tile(_('Won this year'), len(won), 'int', _('awarded %s') % '{:,.0f}'.format(
                sum(won.mapped('ems_awarded_value'))), 'success',
                       self._act(_('Won this year'), 'crm.lead', [('id', 'in', won.ids)])),
            self._tile(_('Win rate'), win_rate, 'pct', _('won vs lost this year'), 'success' if win_rate >= 30 else 'warning'),
            self._tile(_('Average proposal age'), sum(ages) / len(ages) if ages else 0, 'days', _('days since created'), 'muted'),
            self._tile(_('Follow-ups overdue'), len(overdue), 'int', _('proposals to chase'),
                       'danger' if overdue else 'muted', self._act(_('Follow-ups overdue'), 'crm.lead', [('id', 'in', overdue.ids)])),
            self._tile(_('Bid / no-bid pending'), len(undecided), 'int', _('waiting for approval to quote'),
                       'warning' if undecided else 'muted', self._act(_('Bid decision pending'), 'crm.lead', [('id', 'in', undecided.ids)])),
        ]
        groups = Lead._read_group(open_dom, ['stage_id'], ['__count', 'expected_revenue:sum'])
        return {
            'sections': [{'title': _('Pipeline'), 'tiles': tiles}],
            'charts': [
                self._bars(_('Pipeline value by stage'), [{'label': s.name, 'value': v} for s, c, v in groups]),
                self._bars(_('Proposals by stage'), [{'label': s.name, 'value': c} for s, c, v in groups], fmt='int'),
            ],
        }

    # ------------------------------------------------------------------ portfolio
    @api.model
    def _dash_portfolio(self):
        today = fields.Date.context_today(self)
        Project = self.env['project.project'].sudo()
        active = [('ems_closed', '=', False), ('ems_total_value', '>', 0)]
        projects = Project.search(active)
        no_baseline = projects.filtered(lambda p: not p.ems_sale_order_id)
        overdue_pay = self.env['account.move'].sudo().search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')), ('invoice_date_due', '<', today)])
        tiles = [
            self._tile(_('Contracted revenue'), sum(projects.mapped('ems_total_value')), 'money', _('award + approved variations'), 'primary'),
            self._tile(_('Active projects'), len(projects), 'int', False, 'primary', self._act(_('Active projects'), 'project.project', active)),
            self._tile(_('Variations awaiting approval'), sum(projects.mapped('ems_variation_pending')), 'money',
                       _('not in revenue until signed'), 'warning', self._act(_('Variations'), 'ems.variation',
                                                                              [('state', 'in', ('draft', 'submitted'))])),
            self._tile(_('Not yet invoiced'), sum(projects.mapped('ems_uninvoiced')), 'money', _('contract less invoiced'), 'muted'),
            self._tile(_('Payments overdue'), len(overdue_pay), 'int', _('%s outstanding') % '{:,.0f}'.format(
                sum(overdue_pay.mapped('amount_residual'))), 'danger' if overdue_pay else 'success',
                       self._act(_('Overdue invoices'), 'account.move', [('id', 'in', overdue_pay.ids)])),
            self._tile(_('Projects without award baseline'), len(no_baseline), 'int', _('legacy or manual projects'),
                       'warning' if no_baseline else 'muted', self._act(_('No baseline'), 'project.project',
                                                                        [('id', 'in', no_baseline.ids)])),
            self._tile(_('Unapproved timesheet hours'), sum(projects.mapped('ems_hours_unapproved')), 'hours',
                       _('across active projects'), 'warning'),
        ]
        if self.env.user.has_group('ems_base.group_ems_rates'):
            tiles.insert(3, self._tile(_('Forecast margin'), sum(projects.mapped('ems_forecast_margin')), 'money',
                                       _('contract less EAC'), 'success'))
        by_stage = Project._read_group(active, ['stage_id'], ['ems_total_value:sum'])
        by_service = Project._read_group(active, ['ems_service'], ['ems_total_value:sum'], order='ems_total_value:sum desc', limit=8)
        return {
            'sections': [{'title': _('Portfolio'), 'tiles': tiles}],
            'charts': [
                self._bars(_('Contracted revenue by stage'), [{'label': s.name or _('No stage'), 'value': v} for s, v in by_stage]),
                self._bars(_('Contracted revenue by service'), [{'label': sv or _('Unspecified'), 'value': v} for sv, v in by_service]),
            ],
        }

    # ------------------------------------------------------------------ resources
    @api.model
    def _dash_resource(self):
        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        employees = self.env['hr.employee'].sudo().search([('ems_plannable', '=', True)])
        booked = {e: e.ems_booked_pct for e in employees}
        over = [e for e, pct in booked.items() if pct > 100.0 + 1e-6]
        free = [e for e, pct in booked.items() if pct < 50.0]
        Line = self.env['account.analytic.line'].sudo()
        week_dom = [('project_id', '!=', False), ('date', '>=', week_start), ('date', '<=', week_end)]
        actual = sum(Line.search(week_dom).mapped('unit_amount'))
        allocs = self.env['ems.allocation'].sudo().search([('date_from', '<=', week_end), ('date_to', '>=', week_start)])
        planned = sum(a.hours_per_day * a._ems_count_days(max(a.date_from, week_start), min(a.date_to, week_end)) for a in allocs)
        unapproved = Line.search([('project_id', '!=', False), ('ems_state', 'in', ('draft', 'submitted'))])
        tiles = [
            self._tile(_('People planned'), len(employees), 'int', False, 'primary', self._act(_('People'), 'hr.employee', [('id', 'in', employees.ids)], 'kanban,list,form')),
            self._tile(_('Over-booked today'), len(over), 'int', _('above 100% of capacity'), 'danger' if over else 'success',
                       self._act(_('Over-booked'), 'hr.employee', [('id', 'in', [e.id for e in over])], 'kanban,list,form')),
            self._tile(_('Under 50% booked'), len(free), 'int', _('available capacity today'), 'muted'),
            self._tile(_('Planned this week'), planned, 'hours', _('allocations, hours'), 'primary',
                       self._act(_('Allocations'), 'ems.allocation', [('id', 'in', allocs.ids)])),
            self._tile(_('Actual this week'), actual, 'hours', _('timesheet hours'), 'success'),
            self._tile(_('Unapproved timesheets'), sum(unapproved.mapped('unit_amount')), 'hours',
                       _('draft or submitted'), 'warning' if unapproved else 'muted',
                       self._act(_('Unapproved timesheets'), 'account.analytic.line', [('id', 'in', unapproved.ids)])),
            self._tile(_('Tentative allocations'), self.env['ems.allocation'].sudo().search_count([('tentative', '=', True)]), 'int',
                       _('to confirm'), 'muted'),
        ]
        top = sorted(booked.items(), key=lambda kv: -kv[1])[:12]
        return {
            'sections': [{'title': _('Capacity this week'), 'tiles': tiles}],
            'charts': [self._bars(_('Booked today (% of capacity)'),
                                  [{'label': e.name, 'value': pct, 'over': pct > 100.0} for e, pct in top], fmt='pct')],
        }

    # ------------------------------------------------------------------ economics
    @api.model
    def _dash_economics(self):
        projects = self.env['project.project'].sudo().search([('ems_closed', '=', False), ('ems_total_value', '>', 0)])
        figures = projects._ems_economics()
        total = lambda key: sum(f[key] for f in figures.values())  # noqa: E731
        contracted = total('contracted')
        margin = total('forecast_margin')
        tiles = [
            self._tile(_('Original award'), total('baseline'), 'money', _('signed award ex VAT'), 'primary'),
            self._tile(_('Approved variations'), total('variations'), 'money', _('signed by the client'), 'primary'),
            self._tile(_('Planned labour'), total('planned_labour'), 'money', False, 'muted'),
            self._tile(_('Actual labour'), total('actual_labour'), 'money', _('approved timesheets, cost snapshot'), 'primary'),
            self._tile(_('Vendor bills'), total('vendor_billed'), 'money', _('posted'), 'primary'),
            self._tile(_('Open commitments'), total('open_commitment'), 'money', _('POs not yet billed'), 'warning'),
            self._tile(_('Estimate at completion'), total('eac'), 'money', _('actual + remaining'), 'primary'),
            self._tile(_('Forecast margin'), margin, 'money', _('%.1f%% of contracted') % (margin / contracted * 100.0 if contracted else 0.0),
                       'success' if margin >= 0 else 'danger'),
            self._tile(_('Margin after overhead'), total('margin_after_overhead'), 'money', _('overhead allocation applied'), 'primary'),
            self._tile(_('Cash collected'), total('collected'), 'money', _('receipts incl. VAT'), 'success'),
            self._tile(_('Outstanding AR'), total('receivable'), 'money', _('posted unpaid invoices'), 'warning'),
        ]
        by_project = sorted(((projects.browse(pid).display_name, f['forecast_margin']) for pid, f in figures.items()),
                            key=lambda kv: -abs(kv[1]))[:10]
        return {
            'sections': [{'title': _('Project economics (all active projects)'), 'tiles': tiles}],
            'charts': [self._bars(_('Forecast margin by project'), [{'label': n, 'value': v} for n, v in by_project])],
        }

    # ------------------------------------------------------------------ finance
    @api.model
    def _dash_finance(self):
        today = fields.Date.context_today(self)
        Move = self.env['account.move'].sudo()
        out = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]
        eligible = self.env['ems.fee.stage'].sudo().search([('eligible', '=', True)]).filtered(lambda s: s.state == 'todo')
        vat = self._sum('account.move', out, 'amount_tax')
        revenue = self._sum('account.move', out, 'amount_untaxed')
        receipts = self._sum('account.move', out, 'amount_total') - self._sum('account.move', out, 'amount_residual')
        unpaid = self._sum('account.move', out + [('payment_state', 'in', ('not_paid', 'partial'))], 'amount_residual')
        pos = self.env['purchase.order'].sudo().search([('state', 'in', ('purchase', 'done'))])
        billed = sum(pos.mapped('ems_billed_amount'))
        committed = sum(pos.mapped('amount_untaxed'))
        vendor_unpaid = Move.search([('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
                                     ('payment_state', 'in', ('not_paid', 'partial'))])
        tiles = [
            self._tile(_('Milestones ready to invoice'), len(eligible), 'int', _('%s ex VAT') % '{:,.0f}'.format(sum(eligible.mapped('amount'))),
                       'primary' if eligible else 'muted', self._act(_('Ready to invoice'), 'ems.fee.stage', [('id', 'in', eligible.ids)])),
            self._tile(_('Invoiced (ex VAT)'), revenue, 'money', _('revenue, VAT excluded'), 'primary'),
            self._tile(_('VAT charged'), vat, 'money', _('kept out of revenue'), 'muted'),
            self._tile(_('Receipts'), receipts, 'money', _('applied to posted invoices'), 'success'),
            self._tile(_('Unpaid balance'), unpaid, 'money', _('customers'), 'warning'),
            self._tile(_('Vendor POs'), committed, 'money', _('%s billed') % '{:,.0f}'.format(billed), 'primary',
                       self._act(_('Confirmed POs'), 'purchase.order', [('id', 'in', pos.ids)])),
            self._tile(_('PO value not yet billed'), committed - billed, 'money', _('open commitment, counted once'), 'warning'),
            self._tile(_('Vendor bills unpaid'), len(vendor_unpaid), 'int', _('%s due') % '{:,.0f}'.format(sum(vendor_unpaid.mapped('amount_residual'))),
                       'warning', self._act(_('Vendor bills unpaid'), 'account.move', [('id', 'in', vendor_unpaid.ids)])),
        ]
        stage_groups = self.env['ems.fee.stage'].sudo()._read_group([], ['project_id'], ['__count'])
        return {
            'sections': [{'title': _('Invoicing, receipts and vendor matching'), 'tiles': tiles}],
            'charts': [self._bars(_('Fee stages per project (top 10)'),
                                  [{'label': p.display_name, 'value': c} for p, c in sorted(stage_groups, key=lambda x: -x[1])[:10]], fmt='int')],
        }

    # ------------------------------------------------------------------ audit
    @api.model
    def _dash_audit(self):
        week_ago = fields.Datetime.now() - timedelta(days=7)
        Log = self.env['ems.audit.log'].sudo()
        recent = [('date', '>=', week_ago)]
        issues = self.env['ems.data.issue'].sudo()
        crit = issues.search_count([('state', '=', 'open'), ('severity', 'in', ('1_critical', '2_high'))])
        tiles = [
            self._tile(_('Changes last 7 days'), Log.search_count(recent), 'int', False, 'primary',
                       self._act(_('Audit trail'), 'ems.audit.log', recent)),
            self._tile(_('Price changes'), Log.search_count(recent + [('area', '=', 'price')]), 'int', False, 'warning',
                       self._act(_('Price changes'), 'ems.audit.log', recent + [('area', '=', 'price')])),
            self._tile(_('Rate changes'), Log.search_count(recent + [('area', '=', 'rate')]), 'int', False, 'warning',
                       self._act(_('Rate changes'), 'ems.audit.log', recent + [('area', '=', 'rate')])),
            self._tile(_('Milestone triggers'), Log.search_count(recent + [('area', '=', 'trigger')]), 'int', False, 'primary',
                       self._act(_('Trigger changes'), 'ems.audit.log', recent + [('area', '=', 'trigger')])),
            self._tile(_('Baseline changes'), Log.search_count(recent + [('area', '=', 'baseline')]), 'int', False, 'primary',
                       self._act(_('Baseline changes'), 'ems.audit.log', recent + [('area', '=', 'baseline')])),
            self._tile(_('Closures'), Log.search_count(recent + [('area', '=', 'closure')]), 'int', _('task and project closure'), 'muted',
                       self._act(_('Closures'), 'ems.audit.log', recent + [('area', '=', 'closure')])),
            self._tile(_('Open critical data issues'), crit, 'int', _('critical or high'), 'danger' if crit else 'success',
                       self._act(_('Data issues'), 'ems.data.issue', [('state', '=', 'open'), ('severity', 'in', ('1_critical', '2_high'))])),
            self._tile(_('Approval rules'), self.env['ems.approval.rule'].sudo().search_count([]), 'int',
                       _('control gates covered'), 'muted', self._act(_('Approval matrix'), 'ems.approval.rule')),
        ]
        by_area = Log._read_group(recent, ['area'], ['__count'])
        by_user = Log._read_group(recent, ['user_id'], ['__count'], order='__count desc', limit=8)
        labels = dict(Log._fields['area'].selection)
        return {
            'sections': [{'title': _('Who changed what'), 'tiles': tiles}],
            'charts': [
                self._bars(_('Changes by area (7 days)'), [{'label': labels.get(a, a), 'value': c} for a, c in by_area], fmt='int'),
                self._bars(_('Changes by user (7 days)'), [{'label': u.name or '-', 'value': c} for u, c in by_user], fmt='int'),
            ],
        }
