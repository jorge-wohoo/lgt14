from odoo import _, api, fields, models


class IvaAffiliation(models.Model):
    _name = "gt.iva"

    name = fields.Char()
    code = fields.Char()
