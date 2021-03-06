    # -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

from datetime import datetime
import base64
from lxml import etree
import requests
#from import XMLSigner

import logging

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    pdf_fel = fields.Binary('PDF FEL', copy=False)
    pdf_fel_name = fields.Char('Nombre PDF FEL', default='pdf_fel.pdf', size=32)

    def invoice_validate(self):
        for factura in self:    
            if factura.journal_id.generar_fel:
                if factura.firma_fel:
                    raise UserError("La factura ya fue validada, por lo que no puede ser validada nuevamente")

                dte = factura.dte_documento()
                xmls = etree.tostring(dte, xml_declaration=True, encoding="UTF-8").decode("utf-8")
                logging.warn(xmls)
                xmls_base64 = base64.b64encode(xmls.encode("utf-8"))
                
                request_token = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v3/api/login/get_token"
                request_certifica = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v3/api/FelRequestV2"
                if factura.company_id.pruebas_fel:
                    request_token = "https://felgttestaws.digifact.com.gt/gt.com.fel.api.v3/api/login/get_token"
                    request_certifica = "https://felgttestaws.digifact.com.gt/gt.com.fel.api.v3/api/FelRequestV2"

                headers = { "Content-Type": "application/json" }
                data = {
                    "Username": factura.company_id.usuario_fel,
                    "Password": factura.company_id.clave_fel,
                }
                r = requests.post(request_token, json=data, headers=headers, verify=False)
                logging.warn(r.text)
                token_json = r.json()
                if "Token" in token_json:
                    token = token_json["Token"]

                    headers = {
                        "Content-Type": "application/xml",
                        "Authorization": token,
                    }
                    r = requests.post(request_certifica+'?NIT={}&USERNAME={}&TIPO=CERTIFICATE_DTE_XML_TOSIGN&FORMAT=XML%20PDF'.format(factura.company_id.vat.replace('-','').zfill(12), factura.company_id.usuario_fel.split('.')[2]), data=xmls.encode("utf-8"), headers=headers, verify=False)
                    logging.warn(r.text)
                    certificacion_json = r.json()
                    if certificacion_json["Codigo"] == 1:
                        xml_resultado = base64.b64decode(certificacion_json['ResponseDATA1'])
                        logging.warn(xml_resultado)
                        dte_resultado = etree.XML(xml_resultado)

                        numero_autorizacion =  dte_resultado.xpath("//*[local-name() = 'NumeroAutorizacion']")[0]

                        factura.firma_fel = numero_autorizacion.text
                        factura.name = str(numero_autorizacion.get("Serie"))+"-"+str(numero_autorizacion.get("Numero"))
                        factura.serie_fel = numero_autorizacion.get("Serie")
                        factura.numero_fel = numero_autorizacion.get("Numero")
                        factura.documento_xml_fel = xmls_base64
                        factura.resultado_xml_fel = base64.b64encode(xml_resultado)
                        factura.pdf_fel = certificacion_json['ResponseDATA3']
                    else:
                        raise UserError(certificacion_json["ResponseDATA1"])
                else:
                    raise UserError(str(r))

        return super(AccountInvoice,self).invoice_validate()

    def action_cancel(self):
        result = super(AccountInvoice, self).action_cancel()
        if result:
            for factura in self:
                if factura.journal_id.generar_fel:
                    dte = factura.dte_anulacion()
                    if dte:
                        xmls = etree.tostring(dte, xml_declaration=True, encoding="UTF-8")
                        logging.warn(xmls.decode('utf-8'))

                        request_token = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v3/api/login/get_token"
                        request_certifica = "https://felgtaws.digifact.com.gt/gt.com.fel.api.v3/api/FelRequestV2"
                        if factura.company_id.pruebas_fel:
                            request_token = "https://felgttestaws.digifact.com.gt/gt.com.fel.api.v3/api/login/get_token"
                            request_certifica = "https://felgttestaws.digifact.com.gt/gt.com.fel.api.v3/api/FelRequestV2"

                        headers = { "Content-Type": "application/json" }
                        data = {
                            "Username": factura.company_id.usuario_fel,
                            "Password": factura.company_id.clave_fel,
                        }
                        r = requests.post(request_token, json=data, headers=headers, verify=False)
                        logging.warn(r.text)
                        token_json = r.json()

                        if token_json["Token"]:
                            token = token_json["Token"]

                            headers = {
                                "Content-Type": "application/xml",
                                "Authorization": token,
                            }
                            r = requests.post(request_certifica+'?NIT={}&USERNAME={}&TIPO=ANULAR_FEL_TOSIGN&FORMAT=XML'.format(factura.company_id.vat.replace('-','').zfill(12), factura.company_id.usuario_fel.split('.')[2]), data=xmls, headers=headers, verify=False)
                            logging.warn(r.text)
                            certificacion_json = r.json()

                            if certificacion_json["Codigo"] != 1:
                                raise UserError(certificacion_json["ResponseDATA1"])

class AccountJournal(models.Model):
    _inherit = "account.journal"

    generar_fel = fields.Boolean('Generar FEL')

class ResCompany(models.Model):
    _inherit = "res.company"

    usuario_fel = fields.Char('Usuario FEL', copy=False)
    clave_fel = fields.Char('Clave FEL', copy=False)
    pruebas_fel = fields.Boolean('Modo de Pruebas FEL')
