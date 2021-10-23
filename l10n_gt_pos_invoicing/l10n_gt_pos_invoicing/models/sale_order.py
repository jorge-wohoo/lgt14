from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    journal_id = fields.Many2one(
        comodel_name="account.journal",
        domain="[('type', '=', 'sale')]",
    )
    journal_group = fields.Boolean(
        compute="_compute_user_in_journal_group",
        default=False,
    )
    dte_type_id = fields.Many2one(
        comodel_name="gt.dte.type",
        string="Type of DTE",
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=lambda self: self.env["gt.dte.type"].search(
            [
                ("code", "=", "FACT"),
            ]
        ),
    )

    @api.onchange("state")
    def _compute_user_in_journal_group(self):
        for record in self:
            if self.env.user.has_group(
                "l10n_gt_pos_invoicing.group_journal_id_sale_order"
            ):
                record.journal_group = True
            else:
                record.journal_group = False

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        journal = (
            self.env["account.move"]
            .with_context(default_move_type="out_invoice")
            ._get_default_journal()
        )
        invoice_vals["journal_id"] = (self.journal_id.id or journal.id,)
        invoice_vals["dte_type_id"] = self.dte_type_id.id
        return invoice_vals
