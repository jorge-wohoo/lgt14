import uuid
from datetime import datetime

from gt_sat_infile_api.parser import generate_and_parse_query

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    infile_status = fields.Selection(
        [
            ("not_sent", "Not sent"),
            ("done", "Sent successfully"),
            ("error", "Sent with errors"),
            ("annulled", "Annulled"),
            ("annulled_error", "Annulled Error"),
        ],
        string="INFILE status",
        copy=False,
        readonly=True,
    )
    infile_certified_datetime = fields.Datetime(
        string="Certified at",
        copy=False,
        readonly=True,
    )
    infile_xml_uuid = fields.Char(
        string="UUID",
        copy=False,
        readonly=True,
    )
    infile_pdf_link = fields.Char(
        string="Link to pdf",
        compute="_compute_pdf_link",
        readonly=True,
    )
    infile_uuid = fields.Char(
        readonly=True,
        copy=False,
    )

    @api.depends("infile_xml_uuid")
    def _compute_pdf_link(self):
        """Compute the link to the invoice pdf report"""
        INFILE_PDF_LINK = "https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid="
        for move in self:
            move.infile_pdf_link = f"{INFILE_PDF_LINK}{move.infile_xml_uuid}"

    def send_xml_to_sat(self):
        """Implemented Function to send the XML string to SAT through INFILE"""
        login_handler = self.company_id.generate_login_handler()
        xml_string = self.prepare_xml_to_sat()
        self.infile_uuid = uuid.uuid1()
        result = generate_and_parse_query(
            auth_headers=login_handler,
            identifier=self.infile_uuid,
            xml=xml_string,
        )
        if result["res"]:
            xml_certified = result["xml"]
            self.infile_xml_uuid = result["uuid"]
            self.generate_attachment_from_xml_string(xml_certified, {})
            self.infile_status = "done"
        else:
            errors_list = [(error["mensaje_error"] + "\n") for error in result["errors"]]
            self.message_post(
                subject=_("Error sending XML"),
                body="".join(errors_list),
            )
            self.infile_status = "error"

    def send_xml_annulated_to_sat(self):
        """Implemented Function to send the XML string to SAT through INFILE"""
        login_handler = self.company_id.generate_login_handler()
        xml_string = self.prepare_xml_annulated_to_sat()
        if isinstance(xml_string, str):
            xml_string = xml_string.encode("UTF-8")
        result = generate_and_parse_query(
            auth_headers=login_handler,
            identifier=self.infile_xml_uuid,
            xml=xml_string,
        )
        if result["res"]:
            xml_certified = result["xml"]
            self.infile_xml_uuid = result["uuid"]
            self.generate_annulated_attachment_from_xml_string(xml_certified, {})
            self.infile_status = "annulled"
        else:
            errors_list = [(error["mensaje_error"] + "\n") for error in result["errors"]]
            self.message_post(
                subject=_("Error sending XML"),
                body="".join(errors_list),
            )
            self.infile_status = "annulled_error"
