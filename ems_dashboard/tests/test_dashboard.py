from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.ems_dashboard.models.ems_dashboard import KIND_GROUPS


@tagged('post_install', '-at_install')
class TestEmsDashboard(TransactionCase):

    def test_every_dashboard_builds_with_demo_data(self):
        dash = self.env['ems.dashboard']
        for kind in KIND_GROUPS:
            data = dash.get_dashboard(kind)
            self.assertTrue(data['sections'][0]['tiles'], kind)
            for tile in data['sections'][0]['tiles']:
                self.assertIn('value', tile)
                self.assertIsInstance(tile['value'], (int, float), '%s / %s' % (kind, tile['label']))
            for chart in data['charts']:
                for item in chart['items']:
                    self.assertIn('pct', item)

    def test_dashboard_access_follows_groups(self):
        plain = new_test_user(self.env, login='ems_dash_plain', groups='ems_base.group_ems_user')
        dash = self.env['ems.dashboard'].with_user(plain)
        dash.get_dashboard('register')
        with self.assertRaises(AccessError):
            dash.get_dashboard('economics')
        with self.assertRaises(AccessError):
            dash.get_dashboard('audit')
