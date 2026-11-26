from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError

GATES = [
    ('bid', 'Bid / no-bid decision'),
    ('proposal', 'Proposal and discount approval'),
    ('baseline', 'Signed contract baseline'),
    ('po', 'Vendor PO approval'),
    ('variation', 'Variation approval'),
    ('timesheet', 'Timesheet approval'),
    ('invoice', 'Invoice posting'),
    ('closure', 'Project closure'),
]


class EmsApprovalRule(models.Model):
    """Approval matrix: who may pass a control gate, above which amount."""
    _name = 'ems.approval.rule'
    _description = 'EMS Approval Rule'
    _order = 'gate, min_amount'

    name = fields.Char(compute='_compute_name', store=True)
    gate = fields.Selection(GATES, required=True)
    min_amount = fields.Float('From Amount', help='The rule applies to amounts at or above this value.')
    group_id = fields.Many2one('res.groups', 'Approver Group', required=True)
    no_self_approval = fields.Boolean('No Self-approval', default=True,
                                      help='The person who created the record cannot approve it.')
    active = fields.Boolean(default=True)

    @api.depends('gate', 'min_amount', 'group_id')
    def _compute_name(self):
        labels = dict(GATES)
        for rule in self:
            rule.name = '%s >= %s: %s' % (labels.get(rule.gate, ''), rule.min_amount, rule.group_id.display_name or '')

    @api.model
    def check(self, gate, record, amount=0.0):
        """Raise unless the current user may approve ``record`` at ``gate``."""
        user = self.env.user
        if self.env.uid == SUPERUSER_ID or self.env.context.get('ems_skip_approval'):
            return True
        rules = self.sudo().search([('gate', '=', gate), ('min_amount', '<=', amount)], order='min_amount desc')
        if not rules:
            return True
        rule = rules[0]
        if rule.group_id not in user.all_group_ids:
            raise AccessError(_(
                'Approval at gate "%(gate)s" for %(amount).2f needs the group "%(group)s".',
                gate=dict(GATES)[gate], amount=amount, group=rule.group_id.display_name))
        if rule.no_self_approval and record and record.create_uid == user:
            raise AccessError(_(
                'You created %(rec)s, so you cannot approve it yourself (no self-approval at "%(gate)s").',
                rec=record.display_name, gate=dict(GATES)[gate]))
        return True
