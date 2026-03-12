"""
Flask API for PDF Form Field Extractor and JSON Transformer
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import PyPDF2
import os
import tempfile
import base64
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf'}
TMP_DIR = '/tmp' if os.path.exists('/tmp') else tempfile.gettempdir()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_bytes_to_tempfile(pdf_bytes: bytes, suffix: str = '.pdf') -> str:
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=TMP_DIR)
    try:
        tf.write(pdf_bytes)
        tf.flush()
        path = tf.name
    finally:
        tf.close()
    return path

def extract_all_form_fields_from_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        path = save_bytes_to_tempfile(pdf_bytes)
        try:
            fields = extract_all_form_fields_from_path(path)
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
        return fields

    try:
        if hasattr(reader, 'get_fields'):
            form_fields = reader.get_fields()
            if form_fields:
                for field_name, field_obj in form_fields.items():
                    try:
                        if hasattr(field_obj, 'value'):
                            fields[field_name] = field_obj.value
                        elif isinstance(field_obj, dict) and '/V' in field_obj:
                            fields[field_name] = field_obj['/V']
                        else:
                            fields[field_name] = field_obj
                    except Exception:
                        fields[field_name] = field_obj
        elif '/AcroForm' in reader.trailer.get('/Root', {}):
            acro_form = reader.trailer['/Root']['/AcroForm']
            if '/Fields' in acro_form:
                for field in acro_form['/Fields']:
                    field_obj = field.get_object()
                    field_name = field_obj.get('/T')
                    field_value = field_obj.get('/V')
                    if field_name:
                        fields[field_name] = field_value
        else:
            form_fields = reader.get_form_text_fields() if hasattr(reader, 'get_form_text_fields') else None
            if form_fields:
                fields.update(form_fields)
    except Exception as e:
        app.logger.warning(f"Could not extract form fields: {e}")
        try:
            form_fields = reader.get_form_text_fields() if hasattr(reader, 'get_form_text_fields') else None
            if form_fields:
                fields.update(form_fields)
        except Exception:
            pass
    return fields

def extract_all_form_fields_from_path(pdf_path: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        try:
            if hasattr(reader, 'get_fields'):
                form_fields = reader.get_fields()
                if form_fields:
                    for k, v in form_fields.items():
                        try:
                            if hasattr(v, 'value'):
                                fields[k] = v.value
                            elif isinstance(v, dict) and '/V' in v:
                                fields[k] = v['/V']
                            else:
                                fields[k] = v
                        except Exception:
                            fields[k] = v
        except Exception as e:
            app.logger.warning("Fallback extraction failed: %s", e)
    return fields

KEY_MAPPING = {
    'fiscal_name': ('companyInformation', 'fiscalName'),
    'dba_name': ('companyInformation', 'dba'),
    'tax_id': ('companyInformation', 'taxId'),
    'scac': ('companyInformation', 'scacCode'),
    'mc': ('companyInformation', 'mcNumber'),
    'dot': ('companyInformation', 'dotNumber'),
    'main_phone': ('companyInformation', 'mainPhoneNumber'),
    'main_fax': ('companyInformation', 'mainFaxNumber'),
    'main_email': ('companyInformation', 'mainEmailAddress'),
    'asset_based': ('companyInformation', 'companyType', 'assetBased'),
    'broker': ('companyInformation', 'companyType', 'broker3PL'),
    'owner_op': ('companyInformation', 'companyType', 'ownerOP'),
    'other_company': ('companyInformation', 'companyType', 'other'),
    'shipping_address': ('shippingAddress', 'address'),
    'shipping_unit': ('shippingAddress', 'unitBldgFloor'),
    'shipping_city': ('shippingAddress', 'cityTown'),
    'shipping_state': ('shippingAddress', 'stateProvince'),
    'shipping_postal': ('shippingAddress', 'zipPostalCode'),
    'shipping_country': ('shippingAddress', 'country'),
    'billing_equals_shipping': ('billingAddress', 'sameAsShippingAddress'),
    'billing_address': ('billingAddress', 'address'),
    'billing_unit': ('billingAddress', 'unitBldgFloor'),
    'billling_city': ('billingAddress', 'cityTown'),
    'billing_state': ('billingAddress', 'stateProvince'),
    'billing_postal': ('billingAddress', 'zipPostalCode'),
    'billing_country': ('billingAddress', 'country'),
    'remittance_equals_shipping': ('remittanceAddress', 'sameAsShippingAddress'),
    'remittance_equals_billing': ('remittanceAddress', 'sameAsBillingAddress'),
    'remittance_address': ('remittanceAddress', 'address'),
    'remittance_unit': ('remittanceAddress', 'unitBldgFloor'),
    'remittance_city': ('remittanceAddress', 'cityTown'),
    'remittance_state': ('remittanceAddress', 'stateProvince'),
    'remittance_postal': ('remittanceAddress', 'zipPostalCode'),
    'remittance_country': ('remittanceAddress', 'country'),
    'remittance_email': ('remittanceAddress', 'remittanceContactEmailAddress'),
    'bank_name': ('bankInformation', 'bankName'),
    'bank_branch': ('bankInformation', 'bankBranchAddress'),
    'bank_beneficiary': ('bankInformation', 'accountNameOrBeneficiary'),
    'bank_account': ('bankInformation', 'accountNumber'),
    'bank_routing': ('bankInformation', 'routingNumber'),
    'bank_swift': ('bankInformation', 'swiftCode'),
    'bank_currency': ('bankInformation', 'currency'),
    'factoring_name': ('factoringCompanyInformation', 'companyFiscalName'),
    'factoring_address': ('factoringCompanyInformation', 'address'),
    'factoring_contact': ('factoringCompanyInformation', 'contactName'),
    'factoring_phone': ('factoringCompanyInformation', 'contactPhoneNumberAndExtension'),
    'factoring_email': ('factoringCompanyInformation', 'contactEmailAddress'),
    'management_name': ('contactInformation', 'managementEscalations', 'firstNameLastName'),
    'management_title': ('contactInformation', 'managementEscalations', 'title'),
    'management_email': ('contactInformation', 'managementEscalations', 'email'),
    'management_phone': ('contactInformation', 'managementEscalations', 'phone'),
    'dispatch_name': ('contactInformation', 'dispatchOperations', 'firstNameLastName'),
    'dispatch_title': ('contactInformation', 'dispatchOperations', 'title'),
    'dispatch_email': ('contactInformation', 'dispatchOperations', 'email'),
    'dispatch_phone': ('contactInformation', 'dispatchOperations', 'phone'),
    'macropoint': ('digitalTracking', 'macroPoint'),
    'samsara': ('digitalTracking', 'samsara'),
    'p44': ('digitalTracking', 'p44'),
}

def transform_flat_to_structured(flat_data: Dict[str, Any]) -> Dict[str, Any]:
    structured_output: Dict[str, Any] = {"VendorRegistrationForm": {}}

    def clean_value(value):
        if isinstance(value, str):
            s = value.strip()
            if s == '':
                return None
            if s.startswith('/'):
                return s != '/Off'
            return s
        return value

    for flat_key, flat_value in flat_data.items():
        if flat_key in KEY_MAPPING:
            path = KEY_MAPPING[flat_key]
            current = structured_output["VendorRegistrationForm"]
            for p in path[:-1]:
                current = current.setdefault(p, {})
            final_key = path[-1]
            current[final_key] = clean_value(flat_value)

    return structured_output

def ok_response(payload: Dict[str, Any], status: int = 200):
    base = {"success": True, "timestamp": now_iso()}
    base.update(payload)
    return jsonify(base), status

def error_response(message: str, status: int = 400, code: Optional[str] = None):
    body = {"success": False, "timestamp": now_iso(), "error": message}
    if code:
        body["code"] = code
    return jsonify(body), status

def parse_request_pdf():
    content_type = (request.headers.get('Content-Type') or '').lower()
    include_flat = False

    if content_type.startswith('application/pdf'):
        pdf_bytes = request.get_data()
        if not pdf_bytes:
            raise ValueError("Empty PDF body")
        filename = request.headers.get('X-Filename') or 'upload.pdf'
        return pdf_bytes, secure_filename(filename), include_flat

    if request.is_json:
        payload = request.get_json(silent=True)
        if not payload:
            raise ValueError("Empty JSON payload")
        file_b64 = payload.get('file_b64') or payload.get('fileBase64')
        filename = payload.get('filename') or 'upload.pdf'
        include_flat = bool(payload.get('include_flat', False))
        if not file_b64:
            raise ValueError("Missing 'file_b64' in JSON payload")
        try:
            pdf_bytes = base64.b64decode(file_b64)
        except Exception as e:
            raise ValueError(f"Invalid Base64 content: {e}")
        return pdf_bytes, secure_filename(filename), include_flat

    if 'file' not in request.files:
        raise ValueError("Missing 'file' in form-data")
    f = request.files['file']
    if f.filename == '':
        raise ValueError("No file selected")
    if not allowed_file(f.filename):
        raise ValueError("Invalid file type. Only PDF allowed.")
    include_flat = request.form.get('include_flat', 'false').lower() == 'true'
    pdf_bytes = f.read()
    return pdf_bytes, secure_filename(f.filename), include_flat

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "timestamp": now_iso(), "service": "pdf-extractor-api"}), 200

@app.route('/extract', methods=['POST'])
def extract_endpoint():
    try:
        pdf_bytes, filename, include_flat = parse_request_pdf()
        app.logger.info("Received file '%s' size=%d bytes", filename, len(pdf_bytes))
        flat_data = extract_all_form_fields_from_bytes(pdf_bytes)
        structured = transform_flat_to_structured(flat_data)
        response = {"filename": filename, "data": structured}
        if include_flat:
            response["flatData"] = flat_data
        return ok_response(response, 200)
    except ValueError as ve:
        return error_response(str(ve), 400)
    except Exception as e:
        app.logger.exception("Error in /extract")
        return error_response("Processing failed: " + str(e), 500)

@app.route('/extract/flat', methods=['POST'])
def extract_flat_endpoint():
    try:
        pdf_bytes, filename, _ = parse_request_pdf()
        flat_data = extract_all_form_fields_from_bytes(pdf_bytes)
        return ok_response({"filename": filename, "data": flat_data}, 200)
    except ValueError as ve:
        return error_response(str(ve), 400)
    except Exception as e:
        return error_response("Processing failed: " + str(e), 500)

@app.errorhandler(413)
def payload_too_large(e):
    return error_response("File too large. Max 20MB", 413)

@app.errorhandler(404)
def not_found(e):
    return error_response("Endpoint not found", 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)

# ─────────────────────────────────────────────────────────────────────────────
# /pdf/find-invoice-page
# Detecta qué páginas de un PDF multi-hoja contienen una factura,
# y devuelve solo esas páginas como base64.
# ─────────────────────────────────────────────────────────────────────────────
import re
import pdfplumber
from PyPDF2 import PdfWriter, PdfReader

INVOICE_KEYWORDS = [
    'total', 'subtotal', 'amount due', 'balance due', 'invoice total',
    'tax', 'vat', 'iva', 'importe', 'monto', 'total a pagar',
    'invoice', 'factura', 'invoice #', 'invoice no', 'bill of lading',
    'payment', 'pago', 'due date', 'fecha vencimiento', 'fecha de pago',
    'vendor', 'proveedor', 'bill to', 'sold to', 'remit to',
    'freight', 'flete', 'hbl', 'awb', 'container', 'shipper',
]

STRONG_KEYWORDS = [
    'invoice total', 'total amount due', 'amount due',
    'total factura', 'importe total', 'total a pagar',
    'grand total', 'balance due', 'total due',
]

def _score_page(text: str) -> dict:
    t = text.lower()
    score = 0
    matched = []

    for kw in STRONG_KEYWORDS:
        if kw in t:
            score += 10
            matched.append(f'STRONG:{kw}')

    for kw in INVOICE_KEYWORDS:
        if kw in t:
            score += 2
            matched.append(kw)

    if re.search(r'(invoice|factura|bill)\s*[#nno\.]?\s*[\w\-]+', t):
        score += 5
        matched.append('invoice_number_pattern')

    if re.search(r'[\$\€\£]\s*[\d,]+\.?\d*', text):
        score += 5
        matched.append('currency_amount')

    if re.search(r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}', text):
        score += 2
        matched.append('date_pattern')

    words = len(text.split())
    if words < 20:
        score -= 10

    return {'score': score, 'words': words, 'matched': matched}


@app.route('/pdf/find-invoice-page', methods=['POST'])
def find_invoice_page():
    try:
        payload    = request.get_json(silent=True) or {}
        pdf_b64    = payload.get('pdf_base64', '')
        top_n      = int(payload.get('top_n', 1))
        min_score  = int(payload.get('min_score', 8))

        if not pdf_b64:
            return error_response('Missing pdf_base64', 400)

        try:
            pdf_bytes = base64.b64decode(pdf_b64)
        except Exception as e:
            return error_response(f'Invalid base64: {e}', 400)

        pdf_buffer = io.BytesIO(pdf_bytes)

        # ── Puntuar cada página ───────────────────────────────────────────────
        page_scores = []
        with pdfplumber.open(pdf_buffer) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text   = page.extract_text() or ''
                result = _score_page(text)
                page_scores.append({
                    'page_index':       i,
                    'page_number':      i + 1,
                    'score':            result['score'],
                    'words':            result['words'],
                    'matched_keywords': result['matched'],
                    'text_preview':     text[:300].replace('\n', ' ')
                })

        ranked = sorted(page_scores, key=lambda x: x['score'], reverse=True)
        best   = [p for p in ranked if p['score'] >= min_score][:top_n]

        # Fallback: si ninguna supera min_score, devolver la mejor aunque sea
        if not best:
            best = ranked[:1]

        # ── Extraer solo las páginas seleccionadas ────────────────────────────
        pdf_buffer.seek(0)
        reader = PdfReader(pdf_buffer)
        writer = PdfWriter()
        for p in best:
            writer.add_page(reader.pages[p['page_index']])

        out_buf = io.BytesIO()
        writer.write(out_buf)
        out_b64 = base64.b64encode(out_buf.getvalue()).decode('utf-8')

        app.logger.info(
            'find-invoice-page: %d pages total → selected %s',
            total_pages, [p['page_number'] for p in best]
        )

        return ok_response({
            'total_pages':    total_pages,
            'pages_selected': [p['page_number'] for p in best],
            'best_page':      best[0]['page_number'],
            'scores':         best,
            'pdf_base64':     out_b64
        })

    except Exception as e:
        app.logger.exception('Error in /pdf/find-invoice-page')
        return error_response(f'Processing failed: {e}', 500)

# ─────────────────────────────────────────────────────────────────────────────
