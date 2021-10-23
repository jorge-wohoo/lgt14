import base64
from datetime import datetime
from pytz import timezone
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from gt_sat_api import (
    AnulacionDTE,
    DTE,
    Direccion,
    Emisor,
    Frase,
    Impuesto,
    Item,
    Receptor,
    TotalImpuesto,
    Complemento,
)
from gt_sat_api.parsers import dte_to_xml, dte_to_xml_annulled

import logging

_logger = logging.getLogger(__name__)
DIGITS = 10


class AccountMove(models.Model):
    _inherit = "account.move"

    frases_ids = fields.Many2many(comodel_name="gt.frase")
    dte_type_id = fields.Many2one(
        comodel_name="gt.dte.type",
        string="Type of DTE",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    allowed_type_ids = fields.Many2many(
        comodel_name="gt.dte.type",
        compute="_compute_allowed_type_ids",
    )
    emision_datetime = fields.Datetime(
        string="Emision Datetime",
        copy=False,
        readonly=True,
    )
    annulated_date = fields.Datetime(
        string="Emision Datetime",
        copy=False,
        readonly=True,
    )
    regime = fields.Boolean(string="Is Old Regime")
    origin_uuid = fields.Char()
    origin_date = fields.Date()
    need_send_sat = fields.Boolean(
        related="journal_id.enable_sending_to_sat",
    )
    annulment_reason = fields.Text()

    @api.depends("move_type")
    def _compute_allowed_type_ids(self):
        """Method to generate a list of valid dte_type ids and use it to compare in view domain"""
        for move in self:
            if move.move_type in ("out_invoice", "in_invoice"):
                move.allowed_type_ids = self.env["gt.dte.type"].search(
                    [("general_move_type", "=", "invoice")]
                )
            elif move.move_type in ("out_receipt", "in_receipt"):
                move.allowed_type_ids = self.env["gt.dte.type"].search(
                    [("general_move_type", "=", "receipt")]
                )
            else:
                move.allowed_type_ids = self.env["gt.dte.type"].search(
                    [("general_move_type", "=", "refund")]
                )

    def generate_dte_emisor(self):
        """Generate a emisor object to be added in a dte object generation
        Returns:
            Emisor -- The emisor object
        """
        self.ensure_one()
        emisor = Emisor(
            afiliacion_iva=self.company_id.iva_affiliation_id.code,
            codigo_establecimiento=self.company_id.codigo_establecimiento,
            correo_emisor=self.company_id.email,
            nit_emisor=self.company_id.vat,
            nombre_comercial=self.company_id.name,
            nombre_emisor=self.company_id.company_registry,
            direccion=Direccion(
                direccion=self.company_id.street,
                codigo_postal=self.company_id.zip,
                municipio=self.company_id.city,
                departamento=self.company_id.state_id.name,
                pais=self.company_id.country_id.code,
            ),
        )
        return emisor

    def generate_dte_receptor(self):
        """Generate a receptor object to be added in a dte object generation
        Returns:
            Receptor -- The receptor object
        """
        self.ensure_one()
        receptor = Receptor(
            correo_receptor=self.partner_id.email,
            id_receptor=self.partner_id.vat,
            nombre_receptor=self.partner_id.name,
            direccion=Direccion(
                direccion=self.partner_id.street,
                codigo_postal=self.partner_id.zip,
                municipio=self.partner_id.city,
                departamento=self.partner_id.state_id.name,
                pais=self.partner_id.country_id.code,
            ),
        )
        return receptor

    def generate_dte_items(self):
        """Generate list of item objects added in a dte object generation
        Returns:
            list[Item] -- List of items (invoice lines)
        """
        self.ensure_one()
        items = [
            Item(
                bien_o_servicio="B" if line.product_id.type == "consu" else "S",
                numero_linea=index + 1,
                cantidad=line.quantity,
                unidad_medida=line.product_uom_id.name[:3].upper(),
                descripcion=line.product_id.name,
                precio_unitario=round(line.price_unit, DIGITS),
                descuento_porcentual=line.discount,
                impuestos_rate={
                    tax.code_name: (tax.codigo_unidad_gravable, 100 / len(line.tax_ids))
                    for tax in line.tax_ids
                },
            )
            for index, line in enumerate(self.invoice_line_ids)
        ]
        return items

    def generate_dte_complements(self):
        """Generate a list of Complement objects to be added in a dte object generation
        Returns:
            Receptor -- The receptor object
        """
        self.ensure_one()
        complement_list = []
        if self.move_type in ("out_refund", "in_refund"):
            if not self.origin_uuid or not self.origin_date:
                raise ValidationError(_("There is missing information about the original invoice"))
            complemento = Complemento(
                nombre="Notas",
                uri="http://www.sat.gob.gt/fel/notas.xsd",
                regimen=self.regime,
                no_origen=self.origin_uuid,
                fecha_origen=self.origin_date,
                descripcion=self.ref,
                type="nota",
            )
            complement_list.append(complemento)
        return complement_list

    def generate_dte(self):
        """Create a DTE object
        Returns:
            DTE -- A DTE object
        """
        self.ensure_one()
        emisor = self.generate_dte_emisor()
        receptor = self.generate_dte_receptor()
        items = self.generate_dte_items()
        annulated_date = datetime.now().replace(microsecond=0)
        self.emision_datetime = annulated_date
        new_dte = DTE(
            clase_documento="dte",
            codigo_moneda=self.currency_id.name,
            fecha_hora_emision=annulated_date.astimezone(timezone(self.env.user.tz)),
            tipo=self.dte_type_id.code,
            emisor=emisor,
            receptor=receptor,
            frases=[
                Frase(codigo_escenario=frase.code, tipo_frase=frase.type)
                for frase in self.dte_type_id.frases_ids
            ],
            items=items,
            complementos=self.generate_dte_complements(),
        )
        return new_dte

    def generate_xml_from_dte(self, dte):
        """Call to api gt_sat_api to generate xml string from dte object
        Arguments:
            dte {DTE} -- A DTE object
        Returns:
            str -- String of xml parsed from DTE object
        """
        xml = dte_to_xml(dte)
        return xml

    def search_xml_attachments(self):
        """Search for the invoice xml file in attachments
        Returns:
            record -- ir.attachment record or False
        """
        self.ensure_one()
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", self.id),
                ("name", "ilike", ".xml"),
            ],
            limit=1,
        )
        return attachment

    def prepare_xml_to_sat(self):
        """Method that returns the invoice xml string
        Raises:
            ValidationError: If there is a problem with the attachment
        Returns:
            str -- String of xml attachment
        """
        self.ensure_one()
        attachment = self.search_xml_attachments()
        if not attachment:
            raise ValidationError(_("There is no XML attached in the invoice"))
        content = base64.b64decode(attachment.datas)
        return content

    def prepare_xml_annulated_to_sat(self):
        """Method that returns the invoice xml string
        Raises:
            ValidationError: If there is a problem with the attachment
        Returns:
            str -- String of xml attachment
        """
        self.ensure_one()
        attachment = self.search_annulated_xml_attachments()
        if not attachment:
            raise ValidationError(_("There is no XML attached in the invoice"))
        content = base64.b64decode(attachment.datas)
        return content

    def generate_attachment_from_xml_string(self, xml, info=None):
        """Update or create a new xml file as attachment
        Arguments:
            xml {str} -- String of xml invoice
            info {dict} -- Dictionary containing information to generate attachment
        """
        attachment = self.search_xml_attachments()
        if not attachment:
            data_attach = {
                "name": info["fname"],
                "datas": base64.b64encode(xml.encode()),
                "store_fname": info["fname"],
                "description": f"Archivo XML para enviar al SAT - Factura: {info['invoice_name']}",
                "res_model": "account.move",
                "res_id": info["invoice_id"],
                "type": "binary",
            }
            self.env["ir.attachment"].create(data_attach)
        else:
            attachment.datas = base64.b64encode(xml.encode())
            attachment.mimetype = "application/xml"

    def generate_annulated_attachment_from_xml_string(self, xml, info=None):
        """Update or create a new xml file as attachment
        Arguments:
            xml {str} -- String of xml invoice
            info {dict} -- Dictionary containing information to generate attachment
        """
        attachment = self.search_annulated_xml_attachments()
        if not attachment:
            data_attach = {
                "name": info["fname"],
                "datas": base64.b64encode(xml.encode()),
                "store_fname": info["fname"],
                "description": f"Archivo XML para enviar al SAT - Factura: {info['invoice_name']}",
                "res_model": "account.move",
                "res_id": info["invoice_id"],
                "type": "binary",
            }
            self.env["ir.attachment"].create(data_attach)
        else:
            attachment.datas = base64.b64encode(xml.encode())
            attachment.mimetype = "application/xml"

    def generate_dte_xml(self):
        """Generate an xml file per invoice and save them on attachments"""
        self.filled_fields_validation()
        dte = self.generate_dte()
        xml_str = self.generate_xml_from_dte(dte)
        info = {
            "invoice_id": self.id,
            "invoice_name": self.name,
            "fname": dte.tipo + "_" + self.name + ".xml",
        }
        self.generate_attachment_from_xml_string(xml_str, info)

    def send_xml_to_sat(self):
        """Function to send the XML string to SAT"""
        _logger.warning("Not implemented!!!")

    def filled_fields_validation(self):
        """Function to validate the required fields to generate and send the XML"""
        self.ensure_one()
        if not (self.company_id.iva_affiliation_id and self.company_id.codigo_establecimiento):
            raise ValidationError(
                "There's missing information about the company: Check the fields on the DTE section"
            )
        if not (
            self.company_id.email
            and self.company_id.vat
            and self.company_id.company_registry
            and self.company_id.zip
            and self.company_id.street
            and self.company_id.city
            and self.company_id.state_id.name
            and self.company_id.country_id.code
        ):
            raise ValidationError(
                _(
                    "There's missing information about the company: Check the company's registry, email and address"
                )
            )
        if not (
            self.partner_id.email
            and self.partner_id.vat
            and self.partner_id.zip
            and self.partner_id.street
            and self.partner_id.city
            and self.partner_id.state_id.name
            and self.partner_id.country_id.code
        ):
            raise ValidationError(
                _(
                    "There's missing information about the partner: Check the partner's registry, email and address"
                )
            )

    def generate_annulated_dte(self):
        """Create a DTE object
        Returns:
            DTE -- A DTE object
        """
        self.ensure_one()
        emisor = self.generate_dte_emisor()
        receptor = self.generate_dte_receptor()
        annulated_date = datetime.now().replace(microsecond=0)
        self.annulated_date = annulated_date
        new_dte = AnulacionDTE(
            uuid=self.infile_xml_uuid,
            fecha_hora_emision=self.emision_datetime.astimezone(timezone(self.env.user.tz)),
            fecha_hora_anulacion=annulated_date.astimezone(timezone(self.env.user.tz)),
            motivo_anulacion=self.annulment_reason,
            emisor=emisor,
            receptor=receptor,
        )
        return new_dte

    def _post(self, soft=True):
        """Post/Validate the documents"""
        res = super(AccountMove, self)._post(soft)
        self.call_generate_and_send_xml()

        return res

    def call_generate_and_send_xml(self):
        """Call the methods to generate a new XML file and try to send it to SAT"""
        for move in self:
            if not move.journal_id.enable_sending_to_sat:
                continue
            if move.infile_status == "done":
                continue
            move.generate_dte_xml()
            move.send_xml_to_sat()

    def generate_annulate_xml_from_dte(self, dte):
        xml_anulated = dte_to_xml_annulled(dte)
        return xml_anulated

    def generate_dte_xml_annulated(self):
        self.filled_fields_validation()
        dte = self.generate_annulated_dte()
        xml_str = self.generate_annulate_xml_from_dte(dte)
        info = {
            "invoice_id": self.id,
            "invoice_name": self.name,
            "fname": self.name + "_annulated.xml",
        }
        self.generate_annulated_attachment_from_xml_string(xml_str, info)

    def search_annulated_xml_attachments(self):
        """Search for the invoice xml file in attachments
        Returns:
            record -- ir.attachment record or False
        """
        self.ensure_one()
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", self.id),
                ("name", "ilike", "_annulated.xml"),
            ],
            limit=1,
        )
        return attachment

    def call_generate_and_send_xml_annulated(self):
        """Call the methods to generate a new XML file and try to send it to SAT"""
        for move in self:
            move.generate_dte_xml_annulated()
            move.send_xml_annulated_to_sat()

    def button_cancel(self):
        # OVERRIDE
        res = super().button_cancel()
        self.call_generate_and_send_xml_annulated()
        return res
