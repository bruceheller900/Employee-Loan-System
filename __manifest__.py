# -*- coding: utf-8 -*-
{
    'name': "HR Employee Loan",

    'summary': """This Module for Employee Loan""",

    'description':  """This Module for Employee Loan""",

    'author': "InvoZone",
    'website': "http://www.Invozone.com",

    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','hr', 'account','hr_contract_types','hr_payroll'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/hr_loan_seq.xml',
        'data/salary_rule_loan.xml',
        'data/loan_approval_group.xml',
        'views/hr_loan.xml',
        'views/hr_payroll.xml',
        'views/hr_contract.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
