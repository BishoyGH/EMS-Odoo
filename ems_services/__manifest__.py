{
    'name': 'EMS Services & Milestones',
    'version': '20.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'Project services with cost codes, milestones and a service catalogue',
    'depends': ['ems_base', 'project', 'product'],
    'data': [
        'security/ir.access.csv',
        'views/ems_project_service_views.xml',
        'views/project_milestone_views.xml',
        'views/product_views.xml',
        'views/project_views.xml',
        'views/menus.xml',
    ],
    'demo': ['demo/ems_services_demo.xml'],
    'author': 'EMS',
    'license': 'LGPL-3',
    'application': True,
}
