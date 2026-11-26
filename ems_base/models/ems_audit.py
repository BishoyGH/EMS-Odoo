from odoo import api, fields, models


class EmsAuditLog(models.Model):
    """Who changed which sensitive field, when, from what to what (spec section 9/10)."""
    _name = 'ems.audit.log'
    _description = 'EMS Audit Trail'
    _order = 'id desc'
    _rec_name = 'field_label'

    date = fields.Datetime(default=fields.Datetime.now, readonly=True, index=True)
    user_id = fields.Many2one('res.users', 'Changed By', readonly=True, default=lambda s: s.env.user)
    res_model = fields.Char('Model', readonly=True, index=True)
    res_id = fields.Integer('Record ID', readonly=True, index=True)
    record_name = fields.Char('Record', readonly=True)
    area = fields.Selection([
        ('price', 'Price / contract value'), ('rate', 'Cost or charge rate'),
        ('trigger', 'Milestone trigger'), ('baseline', 'WBS / baseline'),
        ('closure', 'Task / project closure'), ('approval', 'Approval'), ('other', 'Other'),
    ], default='other', readonly=True, index=True)
    field_name = fields.Char('Field', readonly=True)
    field_label = fields.Char('Field Label', readonly=True)
    old_value = fields.Char('Old Value', readonly=True)
    new_value = fields.Char('New Value', readonly=True)

    @api.model
    def _log(self, record, fname, old, new, area='other'):
        field = record._fields[fname]
        self.sudo().create({
            'res_model': record._name, 'res_id': record.id,
            'record_name': record.display_name,
            'area': area, 'field_name': fname,
            'field_label': field.string, 'old_value': old, 'new_value': new,
        })

    def action_open_record(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model,
                'res_id': self.res_id, 'view_mode': 'form'}


class EmsAuditMixin(models.AbstractModel):
    """Inherit and set ``_ems_audit_fields = {'field': 'area'}`` to log changes."""
    _name = 'ems.audit.mixin'
    _description = 'EMS Audit Mixin'

    _ems_audit_fields = {}

    @api.model
    def _ems_audit_format(self, record, fname):
        value = record[fname]
        field = record._fields[fname]
        if field.type == 'many2one':
            return value.display_name or ''
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, value) or ''
        if field.type == 'boolean':
            return 'Yes' if value else 'No'
        if field.type == 'many2many':
            return ', '.join(value.mapped('display_name'))
        return '' if value is False or value is None else str(value)

    def write(self, vals):
        watched = [f for f in self._ems_audit_fields if f in vals]
        if not watched or self.env.context.get('ems_no_audit'):
            return super().write(vals)
        before = {rec.id: {f: self._ems_audit_format(rec.sudo(), f) for f in watched} for rec in self}
        res = super().write(vals)
        log = self.env['ems.audit.log']
        for rec in self:
            srec = rec.sudo()
            for fname in watched:
                new = self._ems_audit_format(srec, fname)
                old = before[rec.id][fname]
                if new != old:
                    log._log(srec, fname, old, new, self._ems_audit_fields[fname])
        return res
