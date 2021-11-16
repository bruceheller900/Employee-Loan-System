from collections import defaultdict
from pytz import utc

from addons.resource.models.resource import ROUNDING_FACTOR
from odoo import api, fields, models, _
from datetime import timedelta

from odoo.tools import float_utils
from odoo.exceptions import UserError, AccessError, ValidationError


def timezone_datetime(time):
    if not time.tzinfo:
        time = time.replace(tzinfo=utc)
    return time

class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'
    _description = 'Payslip Input'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description',)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', help="Payslip", index=True)
    sequence = fields.Integer(required=True, index=True, default=10, help="Sequence")
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(help="It is used in computation. For e.g. A rule for sales having "
                               "1% commission of basic salary for per product can defined in expression "
                               "like result = inputs.SALEURO.amount * contract.wage*0.01.")
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
                                  help="The contract for which applied this input")
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Description', defaul='Salary')
    loan_line_id = fields.Many2one('hr.loan.line', string="Loan Installment", help="Loan installment")
    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
                                readonly=True,
                                help='Defines the rules that have to be applied to this payslip, accordingly '
                                     'to the contract chosen. If you let empty the field contract, this field isn\'t '
                                     'mandatory anymore and thus the rules applied will be all the rules set on the '
                                     'structure of all contracts of the employee valid for the chosen period')


class ResourceMixin(models.AbstractModel):
    _inherit = "resource.mixin"

    def get_work_days_data(self, from_datetime, to_datetime, compute_leaves=True, calendar=None, domain=None):
        """
            By default the resource calendar is used, but it can be
            changed using the `calendar` argument.

            `domain` is used in order to recognise the leaves to take,
            None means default value ('time_type', '=', 'leave')

            Returns a dict {'days': n, 'hours': h} containing the
            quantity of working time expressed as days and as hours.
        """
        resource = self.resource_id
        calendar = calendar or self.resource_calendar_id

        # naive datetimes are made explicit in UTC
        if not from_datetime.tzinfo:
            from_datetime = from_datetime.replace(tzinfo=utc)
        if not to_datetime.tzinfo:
            to_datetime = to_datetime.replace(tzinfo=utc)

        # total hours per day: retrieve attendances with one extra day margin,
        # in order to compute the total hours on the first and last days
        from_full = from_datetime - timedelta(days=1)
        to_full = to_datetime + timedelta(days=1)
        intervals = calendar._attendance_intervals(from_full, to_full, resource)
        day_total = defaultdict(float)
        for start, stop, meta in intervals:
            day_total[start.date()] += (stop - start).total_seconds() / 3600

        # actual hours per day
        if compute_leaves:
            intervals = calendar._work_intervals(from_datetime, to_datetime, resource, domain)
        else:
            intervals = calendar._attendance_intervals(from_datetime, to_datetime, resource)
        day_hours = defaultdict(float)
        for start, stop, meta in intervals:
            day_hours[start.date()] += (stop - start).total_seconds() / 3600

        # compute number of days as quarters
        days = sum(
            float_utils.round(ROUNDING_FACTOR * day_hours[day] / day_total[day]) / ROUNDING_FACTOR
            for day in day_hours
        )
        return {
            'days': days,
            'hours': sum(day_hours.values()),
        }

class HrPayrollStructureInherit(models.Model):
    _inherit = 'hr.payroll.structure'
#     """
#     Salary structure used to defined
#     - Basic
#     - Allowances
#     - Deductions
#     """
#     _name = 'hr.payroll.structure'
#     _description = 'Salary Structure'

    @api.model
    def _get_parent(self):
        return self.env.ref('hr_payroll_community.structure_base', False)

    name = fields.Char(required=True)
    code = fields.Char(string='Reference', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
        copy=False, default=lambda self: self.env['res.company']._company_default_get())
    note = fields.Text(string='Description')
    parent_id = fields.Many2one('hr.payroll.structure', string='Parent', default=_get_parent)
    children_ids = fields.One2many('hr.payroll.structure', 'parent_id', string='Children', copy=True)
    rule_ids = fields.Many2many('hr.salary.rule', 'hr_structure_salary_rule_rel', 'struct_id', 'rule_id', string='Salary Rules')
    #
    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create a recursive salary structure.'))

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {}, code=_("%s (copy)") % (self.code))
        return super(HrPayrollStructureInherit, self).copy(default)

    def get_all_rules(self):
        """
        @return: returns a list of tuple (id, sequence) of rules that are maybe to apply
        """
        all_rules = []
        for struct in self:
            all_rules += struct.rule_ids._recursive_search_of_rules()
        return all_rules

    def _get_parent_structure(self):
        parent = self.mapped('parent_id')
        if parent:
            parent = parent._get_parent_structure()
        return parent + self

class HrRuleInputInherit(models.Model):
    _name = 'hr.rule.input'
    _description = 'Salary Rule Input'

    name = fields.Char(string='Description')
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    input_id = fields.Many2one('hr.salary.rule', string='Salary Rule Input', required=True)

    @api.model
    def get_inputs(self, contract_ids, date_from, date_to):

        """This Compute the other inputs to employee payslip.
                           """

        res = super(HrRuleInputInherit, self).get_inputs(contract_ids, date_from, date_to)
        contract_obj = self.env['hr.contract']
        emp_id = contract_obj.browse(contract_ids[0].id).employee_id
        lon_obj = self.env['hr.loan'].search([('employee_id', '=', emp_id.id), ('state', '=', 'approve')])
        for loan in lon_obj:
            for loan_line in loan.loan_lines:
                if date_from <= loan_line.date <= date_to and not loan_line.paid:
                    for result in self:
                        if result.get('code') == 'LO':
                            result['amount'] = loan_line.amount
                            result['loan_line_id'] = loan_line.id
        return res

    def action_payslip_done(self):
        for line in self.input_line_ids:
            if line.loan_line_id:
                line.loan_line_id.paid = True
                line.loan_line_id.loan_id._compute_loan_amount()
        return super(HrRuleInputInherit, self).action_payslip_done()


class HrSalaryRuleInherit(models.Model):
    _inherit = 'hr.salary.rule'
    _order = 'sequence, id'
    _description = 'Salary Rule'


    def _recursive_search_of_rules(self):
        """
        @return: returns a list of tuple (id, sequence) which are all the children of the passed rule_ids
        """
        children_rules = []
        # for rule in self.filtered(lambda rule: rule.child_ids):
        for rule in self.filtered(lambda rule: rule.category_id.children_ids):
            children_rules += rule.child_ids._recursive_search_of_rules()
        return [(rule.id, rule.sequence) for rule in self] + children_rules
