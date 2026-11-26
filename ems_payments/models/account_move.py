from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    ems_project_id = fields.Many2one('project.project', string='EMS Project', index=True, tracking=True)
    ems_fee_stage_id = fields.Many2one('ems.fee.stage', string='Fee Stage', copy=False)
    ems_follow_up_date = fields.Date('Last Follow-up')
    ems_follow_up_method = fields.Selection([('email', 'Email'), ('call', 'Call'), ('meeting', 'Meeting'), ('whatsapp', 'WhatsApp')])
    ems_follow_up_notes = fields.Text('Follow-up Notes')
    ems_client_response = fields.Text('Client Response')
    ems_next_follow_up = fields.Date('Next Follow-up', tracking=True)
    ems_next_follow_up_method = fields.Selection([('email', 'Email'), ('call', 'Call'), ('meeting', 'Meeting'), ('whatsapp', 'WhatsApp')])
    ems_days_overdue = fields.Integer('Days Overdue', compute='_compute_ems_days_overdue')

    @api.depends('invoice_date_due', 'payment_state', 'state')
    def _compute_ems_days_overdue(self):
        today = fields.Date.context_today(self)
        for move in self:
            if (move.move_type == 'out_invoice' and move.state == 'posted' and move.invoice_date_due
                    and move.payment_state not in ('paid', 'in_payment', 'reversed')):
                move.ems_days_overdue = max((today - move.invoice_date_due).days, 0)
            else:
                move.ems_days_overdue = 0

    @api.model
    def _cron_ems_overdue_activities(self):
        """Daily: schedule a follow-up activity on overdue client invoices that have none."""
        today = fields.Date.context_today(self)
        moves = self.search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')), ('invoice_date_due', '<', today)])
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for move in moves:
            if not move.activity_ids and todo:
                move.activity_schedule(
                    activity_type_id=todo.id, summary='Follow up overdue invoice',
                    user_id=move.invoice_user_id.id or self.env.uid)


class AccountMoveDocs(models.Model):
    _inherit = 'account.move'

    ems_document_ids = fields.One2many(
        'ems.document', 'res_id', string='Documents', domain=[('res_model', '=', 'account.move')])
