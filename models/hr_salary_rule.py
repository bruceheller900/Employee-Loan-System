from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from odoo.addons import decimal_precision as dp


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'



    input_ids = fields.One2many('hr.rule.input', 'input_id', string='Inputs', copy=True)
    note = fields.Text(string='Description')

