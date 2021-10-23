from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    motivo_anulacion = fields.Text()

    def retry_annulation(self):
        return super(AccountMove, self).call_generate_and_send_xml_annulated()
