{
    'name': 'EMS Dashboards',
    'version': '20.0.1.0.0',
    'category': 'Services/EMS',
    'summary': 'Register overview, payments, CRM funnel, portfolio, resource, project economics, finance and audit dashboards',
    'depends': ['ems_finance', 'ems_migration'],
    'data': [
        'security/ir.access.csv',
        'views/dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ems_dashboard/static/src/**/*',
        ],
    },
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': False,
}
