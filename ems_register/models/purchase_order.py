from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    ems_project_id = fields.Many2one('project.project', string='EMS Project', tracking=True, index=True)
    ems_quotation_ref = fields.Char('Quotation Ref.')
    ems_quotation_date = fields.Date('Quotation Date')
    ems_tax_treatment = fields.Selection([
        ('uae5', 'UAE VAT 5%'), ('none', 'No VAT'), ('custom', 'Custom per line'),
    ], string='Tax Treatment', default='uae5')
    ems_scope = fields.Html('Scope of Services')
    ems_deliverables = fields.Html('Deliverables')
    ems_exclusions = fields.Html('Exclusions')
    ems_document_location = fields.Char('Document Location')
    # Letter of Appointment
    ems_loa_ref = fields.Char('LOA Ref.', copy=False, readonly=True)
    ems_loa_revision = fields.Integer('LOA Revision', default=0)
    ems_loa_date = fields.Date('LOA Date')
    ems_signed_by = fields.Char('Signed By')
    ems_signed = fields.Boolean('Signed', tracking=True)
    ems_date_start = fields.Date('Start Date')
    ems_completion_basis = fields.Selection([
        ('duration', 'Duration from start'), ('date', 'Fixed date'), ('deliverables', 'On deliverables'),
    ], string='Completion Basis', default='duration')
    ems_duration = fields.Integer('Duration')
    ems_duration_unit = fields.Selection([('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')], default='weeks')
    # Payment terms
    ems_advance_pct = fields.Float('Advance %')
    ems_retention_pct = fields.Float('Retention %')
    ems_retention_release = fields.Char('Retention Release')
    ems_payment_days = fields.Integer('Payment Days', default=30)
    ems_milestone_ids = fields.One2many('ems.po.milestone', 'order_id', string='Payment Milestones')
    ems_milestone_pct = fields.Float('Milestones Total %', compute='_compute_milestone_pct')
    # Conditions
    ems_governing_law = fields.Char('Governing Law')
    ems_forum = fields.Char('Forum')
    ems_liability_cap = fields.Char('Liability Cap')
    ems_insurance = fields.Char('Insurance')
    ems_delay_damages = fields.Char('Delay Damages')
    ems_notice_days = fields.Integer('Notice Days')
    ems_cure_days = fields.Integer('Cure Days')
    ems_restriction_months = fields.Integer('Restriction (months)')
    ems_review_days = fields.Integer('Review Days')
    ems_rep_id = fields.Many2one('res.users', string='EMS Representative')
    ems_notice_email = fields.Char('Notice Email')
    ems_special_conditions = fields.Html('Special Conditions')
    ems_terms = fields.Html('Terms & Conditions')
    ems_next_action = fields.Char('Next Action')
    ems_follow_up_date = fields.Date('Follow-up Date')
    ems_print_count = fields.Integer('Prints', default=0, copy=False)

    @api.depends('ems_milestone_ids.percent')
    def _compute_milestone_pct(self):
        for po in self:
            po.ems_milestone_pct = sum(po.ems_milestone_ids.mapped('percent'))

    @api.constrains('ems_milestone_ids')
    def _check_milestones(self):
        for po in self:
            if po.ems_milestone_ids and po.ems_milestone_pct > 100.01:
                raise ValidationError(_('Payment milestones exceed 100%.'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        icp = self.env['ir.config_parameter'].sudo()
        mapping = {
            'ems_governing_law': 'ems.loa.governing_law', 'ems_forum': 'ems.loa.forum',
            'ems_liability_cap': 'ems.loa.liability_cap', 'ems_insurance': 'ems.loa.insurance',
            'ems_delay_damages': 'ems.loa.delay_damages',
        }
        for fname, key in mapping.items():
            if fname in fields_list:
                val = icp.get_str(key)
                if val:
                    res[fname] = val
        if 'ems_terms' in fields_list:
            clauses = self.env['ems.loa.clause'].search([])
            if clauses:
                res['ems_terms'] = ''.join(
                    '<h4>%d. %s</h4>%s' % (i, c.title, c.body or '') for i, c in enumerate(clauses, 1))
        return res

    @api.onchange('ems_tax_treatment')
    def _onchange_ems_tax_treatment(self):
        if self.ems_tax_treatment == 'custom':
            return
        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'), ('amount_type', '=', 'percent'),
            ('amount', '=', 5.0 if self.ems_tax_treatment == 'uae5' else 0.0),
            ('company_id', '=', self.company_id.id)], limit=1)
        for line in self.order_line:
            line.tax_ids = tax

    def action_issue_loa(self):
        """Issue for signature: number the LOA and mark the order as sent."""
        for po in self:
            if po.state != 'draft':
                raise UserError(_('Only draft orders can be issued for signature.'))
            if not po.ems_loa_ref:
                po.ems_loa_ref = self.env['ir.sequence'].next_by_code('ems.loa') or '/'
            po.ems_loa_date = po.ems_loa_date or fields.Date.context_today(po)
            po.state = 'sent'

    def _ems_check_sub_budget(self):
        for po in self:
            project = po.ems_project_id
            if project and project.ems_sub_budget:
                others = self.search([
                    ('ems_project_id', '=', project.id), ('state', 'in', ('purchase', 'done')),
                    ('id', '!=', po.id)])
                committed = sum(others.mapped('amount_untaxed')) + po.amount_untaxed
                if committed > project.ems_sub_budget:
                    raise UserError(_(
                        'Confirming this order would commit %(c).2f against a sub-consultant budget of %(b).2f on project %(p)s.',
                        c=committed, b=project.ems_sub_budget, p=project.display_name))

    def button_confirm(self):
        self._ems_check_sub_budget()
        return super().button_confirm()

    def action_ems_milestones_from_lines(self):
        for po in self:
            total = po.amount_untaxed
            po.ems_milestone_ids = [(5, 0, 0)] + [
                (0, 0, {'name': line.name.split('\n')[0][:80], 'percent': (line.price_subtotal / total * 100.0) if total else 0.0})
                for line in po.order_line if not line.display_type]


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'product_id' in fields_list and not res.get('product_id'):
            # lump-sum sub-consultancy lines default to the generic service product
            product = self.env.ref('ems_register.product_subconsultancy', raise_if_not_found=False)
            if product:
                res['product_id'] = product.product_variant_id.id
                if 'uom_id' in fields_list and not res.get('uom_id'):
                    res['uom_id'] = product.uom_id.id
        return res
