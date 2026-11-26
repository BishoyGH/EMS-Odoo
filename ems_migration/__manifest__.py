{
    'name': 'EMS Migration & Import Templates',
    'version': '20.0.1.0.0',
    'category': 'Services/EMS',
    'summary': 'Migrate the EMS_PO_Register .dat backup, data-issues report and Excel import templates with data dictionary',
    'depends': ['ems_finance'],
    'data': [
        'security/ir.access.csv',
        'views/ems_data_issue_views.xml',
        'views/ems_migration_run_views.xml',
        'views/ems_import_wizard_views.xml',
        'views/menus.xml',
    ],
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': False,
}
