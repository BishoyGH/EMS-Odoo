{
    'name': 'EMS Payments',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Payment tracker: fee stages, client invoices, follow-ups and customer statements',
    'depends': ['ems_base', 'account'],
    'data': [
        'security/ir.access.csv',
        'views/ems_fee_stage_views.xml',
        'views/account_move_views.xml',
        'views/project_views.xml',
        'report/customer_statement.xml',
        'views/menus.xml',
    ],
    'demo': ['demo/ems_payments_demo.xml'],
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': True,
}
