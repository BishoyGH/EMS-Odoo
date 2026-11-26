from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmsAwardWizard(models.TransientModel):
    _name = 'ems.award.wizard'
    _description = 'Create Award Baseline from Signed PO'

    lead_id = fields.Many2one('crm.lead', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', 'Client', required=True)
    po_ref = fields.Char('Client PO / Award No.', required=True)
    po_date = fields.Date('PO Date', default=fields.Date.context_today)
    ntp_date = fields.Date('NTP Date')
    line_ids = fields.One2many('ems.award.wizard.line', 'wizard_id', string='Scope Lines')
    stage_ids = fields.One2many('ems.award.wizard.stage', 'wizard_id', string='Billing Milestones')
    awarded_total = fields.Float(compute='_compute_totals')
    excluded_total = fields.Float(compute='_compute_totals')
    stage_pct = fields.Float(compute='_compute_totals')

    @api.depends('line_ids.amount', 'line_ids.awarded', 'stage_ids.percent')
    def _compute_totals(self):
        for wiz in self:
            wiz.awarded_total = sum(wiz.line_ids.filtered('awarded').mapped('amount'))
            wiz.excluded_total = sum(wiz.line_ids.filtered(lambda l: not l.awarded).mapped('amount'))
            wiz.stage_pct = sum(wiz.stage_ids.mapped('percent'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead = self.env['crm.lead'].browse(res.get('lead_id') or self.env.context.get('default_lead_id'))
        if lead:
            res['partner_id'] = lead.partner_id.id
            res['line_ids'] = [(0, 0, {'name': _('Awarded scope'), 'amount': lead.ems_awarded_value or lead.ems_last_fee,
                                       'awarded': True})]
            res['stage_ids'] = [
                (0, 0, {'name': 'M1 - Acceptance and NTP', 'percent': 25, 'trigger': 'Acceptance of offer AND NTP'}),
                (0, 0, {'name': 'M2 - Scope and deliverables complete', 'percent': 50,
                        'trigger': 'Completion of scope and deliverables'}),
                (0, 0, {'name': 'M3 - Authority approval', 'percent': 25,
                        'trigger': 'Authority approval and design completion'}),
            ]
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids.filtered('awarded'):
            raise UserError(_('Add at least one awarded scope line.'))
        if self.stage_ids and abs(self.stage_pct - 100.0) > 0.01:
            raise UserError(_('Billing milestones must total 100%% (now %.2f%%).', self.stage_pct))
        product = self.env.ref('ems_finance.product_award').product_variant_id
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'opportunity_id': self.lead_id.id,
            'ems_lead_id': self.lead_id.id,
            'client_order_ref': self.po_ref,
            'ems_award_po_ref': self.po_ref,
            'ems_award_po_date': self.po_date,
            'ems_ntp_date': self.ntp_date,
            'order_line': [(0, 0, {
                'product_id': product.id, 'name': line.name,
                'product_uom_qty': 1 if line.awarded else 0,
                'price_unit': line.amount,
                'ems_not_awarded': not line.awarded,
                'ems_excluded_price': 0.0 if line.awarded else line.amount,
            }) for line in self.line_ids],
        })
        order.action_confirm()
        project = order.ems_project_id
        for seq, stage in enumerate(self.stage_ids, 1):
            self.env['ems.fee.stage'].create({
                'project_id': project.id, 'sequence': seq * 10, 'name': stage.name,
                'trigger': stage.trigger, 'percent': stage.percent,
            })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'project.project', 'res_id': project.id,
            'view_mode': 'form',
        }


class EmsAwardWizardLine(models.TransientModel):
    _name = 'ems.award.wizard.line'
    _description = 'Award Scope Line'

    wizard_id = fields.Many2one('ems.award.wizard', required=True, ondelete='cascade')
    name = fields.Char('Scope Item', required=True)
    amount = fields.Float('Amount (ex VAT)')
    awarded = fields.Boolean('Awarded', default=True,
                             help='Untick for proposal items the client did not award: they stay excluded from revenue.')


class EmsAwardWizardStage(models.TransientModel):
    _name = 'ems.award.wizard.stage'
    _description = 'Award Billing Milestone'

    wizard_id = fields.Many2one('ems.award.wizard', required=True, ondelete='cascade')
    name = fields.Char('Milestone', required=True)
    percent = fields.Float('%')
    trigger = fields.Char('Trigger Evidence')
