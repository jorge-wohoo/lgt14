from odoo import _, api, fields, models


class Frase(models.Model):
    _name = "gt.frase"

    type = fields.Integer()
    name = fields.Char(string="Tipo")
    code = fields.Integer()
    setting = fields.Char(string="Escenario")
