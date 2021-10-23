from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def create_invoices(self):
        res = super(SaleAdvancePaymentInv, self).create_invoices()
        sale_orders = self.env["sale.order"].browse(self._context.get("active_ids", []))
        for sale in sale_orders:
            for invoices in sale.invoice_ids:
                if invoices.infile_status == "not_sent":
                    invoices.action_post()
        return res
