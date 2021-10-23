from datetime import datetime
from odoo.tests import TransactionCase

from gt_sat_api import (
    DTE,
    Direccion,
    Emisor,
    Frase,
    Impuesto,
    Item,
    Receptor,
    TotalImpuesto,
)

import logging

_logger = logging.getLogger(__name__)


class ApiTest(TransactionCase):
    def dte_demo(self):
        """Creates basic DTE"""
        emisor = Emisor(
            afiliacion_iva="GEN",
            codigo_establecimiento=1,
            correo_emisor="info@yourcompany.com",
            nit_emisor="9847847",
            nombre_comercial="YourCompany",
            nombre_emisor="YourCompany, SOCIEDAD ANONIMA",
            direccion=Direccion(
                direccion="CUIDAD",
                codigo_postal="01001",
                municipio="GUATEMALA",
                departamento="Guatemala",
                pais="GT",
            ),
        )
        receptor = Receptor(
            correo_receptor="azure.Interior24@example.com",
            id_receptor="76365204",
            nombre_receptor="Azure Interior",
            direccion=Direccion(
                direccion="CUIDAD",
                codigo_postal="01001",
                municipio="GUATEMALA",
                departamento="Guatemala",
                pais="GT",
            ),
        )
        items = [
            Item(
                bien_o_servicio="B",
                numero_linea=1,
                cantidad=1.00,
                unidad_medida="Units",
                descripcion="Corner Desk Right Sit",
                precio_unitario=147.00,
                precio=147.00,
                descuento=0.00,
                impuestos=[
                    Impuesto(
                        nombre_corto="IVA",
                        codigo_unidad_gravable=1,
                        monto_gravable=131.25,
                        monto_impuesto=15.75,
                    ),
                ],
                total=147.00,
            ),
        ]
        new_dte = DTE(
            clase_documento="dte",
            codigo_moneda="GTQ",
            fecha_hora_emision=datetime.fromisoformat("2021-05-21T01:10:21+02:00"),
            tipo="FACT",
            emisor=emisor,
            receptor=receptor,
            frases=[Frase(codigo_escenario=1, tipo_frase=1)],
            items=items,
        )
        return new_dte

    def test_dte_creation(self):
        invoice = self.env["account.move"].browse(1)
        assert invoice
        assert invoice.generate_dte()

    def test_dte_filled(self):
        invoice = self.env["account.move"].browse(1)
        demo = self.dte_demo()
        assert invoice.generate_dte()[0].emisor == demo.emisor
        assert invoice.generate_dte()[0].receptor == demo.receptor
        assert (
            invoice.generate_dte()[0].fecha_hora_emision.isoformat()
            == demo.fecha_hora_emision.isoformat()
        )
        assert invoice.generate_dte()[0].clase_documento == demo.clase_documento
        assert invoice.generate_dte()[0].codigo_moneda == demo.codigo_moneda
        assert invoice.generate_dte()[0].tipo == demo.tipo
        assert invoice.generate_dte()[0].frases == demo.frases
        assert invoice.generate_dte()[0].totales_impuestos == demo.totales_impuestos
        assert invoice.generate_dte()[0].gran_total == demo.gran_total
