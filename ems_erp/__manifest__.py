{
    'name': 'EMS ERP',
    'version': '20.0.1.0.0',
    'category': 'Services/EMS',
    'summary': 'Installs the full EMS suite: proposals, register, payments, services, planning, people',
    'assets': {'web.assets_tests': ['ems_erp/static/tests/tours/*']},
    'depends': [
        'ems_base', 'ems_proposals', 'ems_register', 'ems_payments',
        'ems_services', 'ems_planning', 'ems_people', 'ems_finance', 'ems_migration', 'ems_dashboard',
    ],
    'data': [],
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': True,
}
