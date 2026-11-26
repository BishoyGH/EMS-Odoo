{
    'name': 'EMS ERP',
    'version': '20.0.1.0.0',
    'category': 'Services/EMS',
    'summary': 'Installs the full EMS suite: proposals, register, payments, services, planning, people',
    'depends': [
        'ems_base', 'ems_proposals', 'ems_register', 'ems_payments',
        'ems_services', 'ems_planning', 'ems_people', 'ems_finance', 'ems_migration',
    ],
    'data': [],
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': True,
}
