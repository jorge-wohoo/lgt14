from odoo import _, api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    enable_sending_to_sat = fields.Boolean(
        string="Send invoices to SAT",
        default=False,
    )
