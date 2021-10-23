from odoo import _, api, fields, models


class Company(models.Model):
    _inherit = "res.company"

    iva_affiliation_id = fields.Many2one(comodel_name="gt.iva", string="Afiliacion IVA")
    codigo_establecimiento = fields.Integer()
