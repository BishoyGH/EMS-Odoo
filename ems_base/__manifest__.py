{
    'name': 'EMS Base',
    'version': '20.0.1.0.0',
    'category': 'Services/EMS',
    'summary': 'EMS shared foundation: security groups, partner and project extensions',
    'depends': ['base', 'mail', 'contacts', 'project', 'account'],
    'data': [
        'security/ems_security.xml',
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'views/res_partner_views.xml',
        'views/project_views.xml',
        'views/menus.xml',
    ],
    'demo': ['demo/ems_base_demo.xml'],
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': False,
}
