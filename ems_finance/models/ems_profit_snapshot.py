from odoo import api, fields, models, _


class EmsProfitSnapshot(models.Model):
    """Dated profit snapshot per project (spec: baseline, variations, labour, third party, billed, collected, margin)."""
    _name = 'ems.profit.snapshot'
    _description = 'Project Profit Snapshot'
    _order = 'date desc, project_id'

    project_id = fields.Many2one('project.project', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='project_id.partner_id', store=True)
    date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    currency_id = fields.Many2one(related='project_id.ems_currency_id', store=True)
    baseline = fields.Monetary('Baseline Revenue')
    variations = fields.Monetary('Approved Variations')
    contracted = fields.Monetary('Contracted Revenue')
    invoiced = fields.Monetary('Invoiced (ex VAT)')
    collected = fields.Monetary('Collected (incl. VAT)')
    receivable = fields.Monetary('Outstanding AR')
    planned_labour = fields.Monetary('Planned Labour', groups='ems_base.group_ems_rates')
    actual_labour = fields.Monetary('Actual Labour', groups='ems_base.group_ems_rates')
    vendor_billed = fields.Monetary('Vendor Bills Posted')
    open_commitment = fields.Monetary('Open Commitments')
    actual_direct = fields.Monetary('Actual Direct Cost', groups='ems_base.group_ems_rates')
    etc_labour = fields.Monetary('ETC Labour', groups='ems_base.group_ems_rates')
    eac = fields.Monetary('EAC', groups='ems_base.group_ems_rates')
    forecast_margin = fields.Monetary('Forecast Margin', groups='ems_base.group_ems_rates')
    forecast_margin_pct = fields.Float('Forecast Margin %', groups='ems_base.group_ems_rates')
    realised_margin = fields.Monetary('Realised Margin', groups='ems_base.group_ems_rates')
    overhead = fields.Monetary('Overhead Allocation', groups='ems_base.group_ems_rates')
    margin_after_overhead = fields.Monetary('Margin after Overhead', groups='ems_base.group_ems_rates')
    cost_variance = fields.Monetary('Cost Variance', groups='ems_base.group_ems_rates')
    hours_budget = fields.Float('Budget Hours')
    hours_actual = fields.Float('Approved Hours')

    @api.model
    def _take(self, projects):
        figures = projects._ems_economics()
        vals_list = []
        for project in projects:
            f = figures[project.id]
            vals = {'project_id': project.id}
            for fname in self._fields:
                if fname in f:
                    vals[fname] = f[fname]
            vals['overhead'] = f['overhead']
            vals_list.append(vals)
        return self.sudo().create(vals_list)
