// Fixed sample data for the prototype. Every company, VAT id and IBAN is invented; the IBANs
// carry valid check digits so a reviewer can paste them into a checker. The shape follows what
// A6b's API returns: the canonical invoice fields, the check results, the decision and the
// proposal row (SPEC 3.12, 6). Agent texts are adapted from the hand-written A5 eval fixtures.

const BUYER = { name: "Beispiel Handels GmbH", street: "Beispielweg 12", postcode: "50667", city: "Köln" };
const EXTRACT_THRESHOLD = 0.9;
const GL_THRESHOLD = 0.9;
const TODAY = "2026-11-03";

const SKR03 = {
  "0650": "Büroeinrichtung",
  "0670": "Geringwertige Wirtschaftsgüter",
  "3300": "Wareneingang 7 % Vorsteuer",
  "3400": "Wareneingang 19 % Vorsteuer",
  "4210": "Miete",
  "4240": "Gas, Strom, Wasser",
  "4260": "Instandhaltung betrieblicher Räume",
  "4360": "Versicherungen",
  "4530": "Laufende Kfz-Betriebskosten",
  "4610": "Werbekosten",
  "4650": "Bewirtungskosten",
  "4660": "Reisekosten Arbeitnehmer",
  "4800": "Reparaturen und Instandhaltung",
  "4806": "Wartungskosten für Hard- und Software",
  "4910": "Porto",
  "4920": "Telefon",
  "4930": "Bürobedarf",
  "4940": "Zeitschriften und Bücher",
  "4945": "Fortbildungskosten",
  "4950": "Rechts- und Beratungskosten",
  "4955": "Buchführungskosten",
  "4964": "Lizenzen und Software-Überlassung",
  "4970": "Nebenkosten des Geldverkehrs",
  "4980": "Betriebsbedarf",
  "4985": "Werkzeuge und Kleingeräte",
};

// Vendor master data (table `vendors`): the IBAN here is what BANK_DETAILS_CHANGED compares with.
const VENDORS = {
  DE100000016: { name: "Muster Bürobedarf GmbH", iban: "DE89370400440532013000",
    address: { street: "Lindenallee 8", postcode: "04109", city: "Leipzig" } },
  DE100000024: { name: "Beispiel IT-Service GmbH", iban: "DE09100100101234567890",
    address: { street: "Am Technologiepark 3", postcode: "28359", city: "Bremen" } },
  DE100000032: { name: "Muster Logistik GmbH", iban: "DE68200505504711000815",
    address: { street: "Hafenstraße 21", postcode: "20457", city: "Hamburg" } },
  DE100000049: { name: "Beispiel Kaffee KG", iban: "DE68370501981990123456",
    address: { street: "Röstereiweg 5", postcode: "50823", city: "Köln" } },
  DE100000057: { name: "Muster Haustechnik GmbH", iban: "DE44500105175531007788",
    address: { street: "Werkstraße 14", postcode: "60314", city: "Frankfurt am Main" } },
  DE100000008: { name: "Beispiel Software AG", iban: "DE89430609679988776655",
    address: { street: "Innovationsring 2", postcode: "70565", city: "Stuttgart" } },
  DE100000065: { name: "Muster Druck & Werbung GmbH", iban: "DE79600501017402001122",
    address: { street: "Druckerweg 7", postcode: "90429", city: "Nürnberg" } },
};

// Rule texts a proposal can cite (table `rule_chunks`). The AP policy texts are copied from
// data/rules/ap_policy.md; statute texts are not reproduced in the prototype.
const RULE_CHUNKS = {
  "AP-automatic-booking": "An invoice is booked without a person only when all of the following hold: structured invoices (XRechnung, ZUGFeRD) were accepted by the KoSIT validator; invoices read from PDF or scan have every required field extracted with high confidence; every content and arithmetic check passes; the purchase order matches the invoice; the suggested general-ledger account (SKR03) has a probability above the set threshold.",
  "AP-price-tolerance": "The unit price on the invoice may differ from the purchase order price by at most 2 percent in either direction. A larger deviation goes to review (PRICE_OUTSIDE_TOLERANCE).",
  "AP-goods-receipt": "Where goods receipts exist, the invoiced quantity must not exceed the quantity received. Invoices above it go to review (QUANTITY_ABOVE_RECEIPT). A purchase order without goods receipts is matched on price and reference only.",
  "AP-bank-details": "If the IBAN on the invoice differs from the IBAN in the vendor master record, the invoice always goes to review (BANK_DETAILS_CHANGED), whatever the other checks say. The reviewer confirms the change with the vendor by a known channel before it is accepted.",
  "AP-duplicates": "An invoice is a duplicate if the same seller VAT id and invoice number were received before, or if the same seller sent the same gross amount with an issue date within 7 days of an earlier invoice. Duplicates are not booked (DUPLICATE_INVOICE).",
  "AP-mandatory-content": "Invoices must carry the details required by §14 Abs. 4 UStG. Invoices up to a gross amount of 250 EUR need fewer details (§33 UStDV). A missing mandatory field goes to review; the reviewer asks the vendor for a corrected invoice.",
  "AP-vendor-master-data": "The seller must exist in the vendor master data. An unknown vendor always goes to review (UNKNOWN_VENDOR). Vendors are not created from an invoice.",
  "UStG-14-4": null,
};

function email(number, date, request) {
  return `Sehr geehrte Damen und Herren,\n\nzu Ihrer Rechnung ${number} vom ${date} bitten wir um eine korrigierte Rechnung: ${request}\n\nMit freundlichen Grüßen\nKreditorenbuchhaltung`;
}

// Fields hold [value, confidence]. For XML formats the evidence is the element (BT id, XPath);
// for PDF and scan it is page 1 and the quote as printed, which the page view marks.
const INVOICES = [
  {
    id: 2001, received: "2026-10-28", format: "ubl", status: "auto_booked", vendor: "DE100000024",
    fields: {
      seller_name: ["Beispiel IT-Service GmbH", 1], seller_vat_id: ["DE100000024", 1],
      seller_address: [VENDORS.DE100000024.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE09100100101234567890", 1], number: ["IT-26-0931", 1],
      issue_date: ["2026-10-27", 1], delivery_date: ["2026-10-20", 1], due_date: ["2026-11-26", 1],
      po_number: ["PO-2026-0142", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["1250.00", 1], vat_total: ["237.50", 1], gross_total: ["1487.50", 1],
      amount_due: ["1487.50", 1],
    },
    lines: [{ id: "1", item: "Wartung Server, Oktober 2026", qty: "1", price: "1250.00", net: "1250.00", rate: "19", ref: "1" }],
    kosit: true, gl: ["4806", 0.97], reasons: [], failed: [],
    po: { number: "PO-2026-0142", lines: [{ id: "1", desc: "Wartung Server, monatlich", qty: "1", price: "1250.00", received: null }] },
    history: [{ number: "IT-26-0874", date: "2026-09-28", gross: "1487.50", gl: "4806" }],
    proposal: null,
  },
  {
    id: 2002, received: "2026-10-30", format: "zugferd_pdf", status: "auto_booked", vendor: "DE100000032",
    fields: {
      seller_name: ["Muster Logistik GmbH", 1], seller_vat_id: ["DE100000032", 1],
      seller_address: [VENDORS.DE100000032.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE68200505504711000815", 1], number: ["ML-118204", 1],
      issue_date: ["2026-10-29", 1], delivery_date: ["2026-10-29", 1], due_date: ["2026-11-12", 1],
      po_number: ["PO-2026-0150", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["386.40", 1], vat_total: ["73.42", 1], gross_total: ["459.82", 1],
      amount_due: ["459.82", 1],
    },
    lines: [{ id: "1", item: "Paketversand national", qty: "46", price: "8.40", net: "386.40", rate: "19", ref: "1" }],
    kosit: true, gl: ["4910", 0.94], reasons: [], failed: [],
    po: { number: "PO-2026-0150", lines: [{ id: "1", desc: "Paketversand national", qty: "60", price: "8.40", received: "46" }] },
    history: [{ number: "ML-117960", date: "2026-09-30", gross: "389.80", gl: "4910" }],
    proposal: null,
  },
  {
    id: 2003, received: "2026-10-31", format: "pdf", status: "auto_booked", vendor: "DE100000049",
    fields: {
      seller_name: ["Beispiel Kaffee KG", 0.99], seller_vat_id: ["DE100000049", 0.98],
      seller_address: [VENDORS.DE100000049.address, 0.97], buyer_name: [BUYER.name, 0.99],
      iban: ["DE68370501981990123456", 0.97], number: ["2026-1187", 0.99],
      issue_date: ["2026-10-30", 0.98], delivery_date: ["2026-10-30", 0.96], due_date: ["2026-11-13", 0.97],
      po_number: ["PO-2026-0153", 0.98], buyer_reference: null,
      tax_exclusive_total: ["84.00", 0.99], vat_total: ["5.88", 0.98], gross_total: ["89.88", 0.99],
      amount_due: ["89.88", 0.98],
    },
    lines: [{ id: "1", item: "Kaffeebohnen Crema, 1 kg", qty: "6", price: "14.00", net: "84.00", rate: "7", ref: "1" }],
    kosit: null, gl: ["4650", 0.93], reasons: [], failed: [],
    po: { number: "PO-2026-0153", lines: [{ id: "1", desc: "Kaffeebohnen Crema, 1 kg", qty: "6", price: "14.00", received: "6" }] },
    history: [{ number: "2026-1022", date: "2026-09-29", gross: "89.88", gl: "4650" }],
    proposal: null,
  },
  {
    id: 2004, received: "2026-10-22", format: "ubl", status: "approved", decided: "2026-10-23", vendor: "DE100000057",
    fields: {
      seller_name: ["Muster Haustechnik GmbH", 1], seller_vat_id: ["DE100000057", 1],
      seller_address: [VENDORS.DE100000057.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE44500105175531007788", 1], number: ["HT-2026-077", 1],
      issue_date: ["2026-10-21", 1], delivery_date: ["2026-10-17", 1], due_date: ["2026-11-04", 1],
      po_number: ["PO-2026-0131", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["640.00", 1], vat_total: ["121.60", 1], gross_total: ["761.60", 1],
      amount_due: ["761.60", 1],
    },
    lines: [{ id: "1", item: "Wartung Heizungsanlage", qty: "1", price: "640.00", net: "640.00", rate: "19", ref: "1" }],
    kosit: true, gl: ["4260", 0.71], reasons: ["LOW_GL_CONFIDENCE"], failed: [],
    po: { number: "PO-2026-0131", lines: [{ id: "1", desc: "Wartung Heizungsanlage", qty: "1", price: "640.00", received: "1" }] },
    history: [],
    proposal: {
      action: "approve_booking", gl_account: "4260", citations: ["AP-automatic-booking"], reasons: [],
      explanation: "All checks pass; only the account suggestion was below the threshold. Heating maintenance in the company's own rooms fits 4260 (Instandhaltung betrieblicher Räume).",
      vendor_email_de: null,
    },
  },
  {
    id: 2005, received: "2026-10-23", format: "cii", status: "rejected", decided: "2026-10-24", vendor: "DE100000008",
    fields: {
      seller_name: ["Beispiel Software AG", 1], seller_vat_id: ["DE100000008", 1],
      seller_address: [VENDORS.DE100000008.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE89430609679988776655", 1], number: ["BS-2026-3301", 1],
      issue_date: ["2026-10-22", 1], delivery_date: null, due_date: ["2026-11-21", 1],
      po_number: ["PO-2026-0128", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["2400.00", 1], vat_total: ["456.00", 1], gross_total: ["2856.00", 1],
      amount_due: ["2856.00", 1],
    },
    lines: [{ id: "1", item: "Lizenz Lagerverwaltung, 12 Monate", qty: "1", price: "2400.00", net: "2400.00", rate: "19", ref: "1" }],
    kosit: true, gl: ["4964", 0.96], reasons: ["MISSING_DELIVERY_DATE"],
    failed: [{ code: "MISSING_DELIVERY_DATE", message: "§14 Abs. 4 Nr. 6 delivery date or period: missing" }],
    po: { number: "PO-2026-0128", lines: [{ id: "1", desc: "Lizenz Lagerverwaltung", qty: "1", price: "2400.00", received: null }] },
    history: [],
    proposal: {
      action: "request_correction", gl_account: "4964", citations: ["UStG-14-4"], reasons: [],
      explanation: "The invoice gives no date of delivery or service period; § 14 Abs. 4 UStG requires it.",
      vendor_email_de: email("BS-2026-3301", "22.10.2026", "Bitte geben Sie das Liefer- oder Leistungsdatum bzw. den Leistungszeitraum an."),
    },
  },
  {
    id: 1011, received: "2026-10-28", format: "pdf", status: "open", vendor: "DE100000016",
    fields: {
      seller_name: ["Muster Bürobedarf GmbH", 0.99], seller_vat_id: ["DE100000016", 0.98],
      seller_address: [VENDORS.DE100000016.address, 0.97], buyer_name: [BUYER.name, 0.99],
      iban: ["DE89370400440532013000", 0.97], number: ["RE-2026-0412", 0.99],
      issue_date: ["2026-10-26", 0.98], delivery_date: ["2026-10-22", 0.97], due_date: ["2026-11-25", 0.97],
      po_number: ["PO-2026-0117", 0.98], buyer_reference: null,
      tax_exclusive_total: ["448.00", 0.99], vat_total: ["85.12", 0.98], gross_total: ["533.12", 0.99],
      amount_due: ["533.12", 0.98],
    },
    lines: [{ id: "1", item: "Toner schwarz", qty: "4", price: "112.00", net: "448.00", rate: "19", ref: "1" }],
    kosit: null, gl: ["4930", 0.95], reasons: ["PRICE_OUTSIDE_TOLERANCE"],
    failed: [{ code: "PRICE_OUTSIDE_TOLERANCE", message: "unit price deviates more than 2% from the PO: lines 1" }],
    po: { number: "PO-2026-0117", lines: [{ id: "1", desc: "Toner schwarz", qty: "4", price: "105.00", received: "4" }] },
    history: [
      { number: "RE-2026-0377", date: "2026-08-12", gross: "249.90", gl: "4930" },
      { number: "RE-2026-0301", date: "2026-07-09", gross: "512.40", gl: "4930" },
    ],
    proposal: {
      action: "request_correction", gl_account: "4930", citations: ["AP-price-tolerance"], reasons: [],
      explanation: "The unit price of 112.00 EUR is 6.7 % above the ordered 105.00 EUR; the policy allows 2 %.",
      vendor_email_de: email("RE-2026-0412", "26.10.2026", "Der Stückpreis von 112,00 EUR weicht vom bestellten Preis von 105,00 EUR ab (Bestellung PO-2026-0117)."),
    },
  },
  {
    id: 1001, received: "2026-10-29", format: "pdf", status: "open", vendor: "DE100000065",
    fields: {
      seller_name: ["Muster Druck & Werbung GmbH", 0.99], seller_vat_id: null,
      seller_address: [VENDORS.DE100000065.address, 0.97], buyer_name: [BUYER.name, 0.98],
      iban: ["DE79600501017402001122", 0.96], number: ["MDW-26-0558", 0.99],
      issue_date: ["2026-10-27", 0.98], delivery_date: ["2026-10-24", 0.96], due_date: ["2026-11-10", 0.97],
      po_number: ["PO-2026-0139", 0.98], buyer_reference: null,
      tax_exclusive_total: ["420.00", 0.99], vat_total: ["79.80", 0.98], gross_total: ["499.80", 0.99],
      amount_due: ["499.80", 0.98],
    },
    lines: [{ id: "1", item: "Flyer A5, 5.000 Stück", qty: "1", price: "420.00", net: "420.00", rate: "19", ref: "1" }],
    kosit: null, gl: ["4610", 0.92], reasons: ["MISSING_VAT_ID"],
    failed: [{ code: "MISSING_VAT_ID", message: "§14 Abs. 4 Nr. 2 seller USt-IdNr or Steuernummer: missing" }],
    po: { number: "PO-2026-0139", lines: [{ id: "1", desc: "Flyer A5, 5.000 Stück", qty: "1", price: "420.00", received: "1" }] },
    history: [{ number: "MDW-26-0412", date: "2026-08-30", gross: "702.10", gl: "4610" }],
    proposal: {
      action: "request_correction", gl_account: "4610", citations: ["UStG-14-4", "AP-mandatory-content"], reasons: [],
      explanation: "The invoice states neither the seller's VAT id nor a tax number, which § 14 Abs. 4 UStG requires on an invoice above 250 EUR.",
      vendor_email_de: email("MDW-26-0558", "27.10.2026", "Es fehlen Ihre Umsatzsteuer-Identifikationsnummer oder Ihre Steuernummer."),
    },
  },
  {
    id: 1019, received: "2026-10-30", format: "ubl", status: "open", vendor: "DE100000024",
    fields: {
      seller_name: ["Beispiel IT-Service GmbH", 1], seller_vat_id: ["DE100000024", 1],
      seller_address: [VENDORS.DE100000024.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE67700202702233445566", 1], number: ["IT-26-0957", 1],
      issue_date: ["2026-10-29", 1], delivery_date: ["2026-10-27", 1], due_date: ["2026-11-28", 1],
      po_number: ["PO-2026-0148", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["980.00", 1], vat_total: ["186.20", 1], gross_total: ["1166.20", 1],
      amount_due: ["1166.20", 1],
    },
    lines: [{ id: "1", item: "Einrichtung Arbeitsplatzrechner", qty: "7", price: "140.00", net: "980.00", rate: "19", ref: "1" }],
    kosit: true, gl: ["4806", 0.96], reasons: ["BANK_DETAILS_CHANGED"],
    failed: [{ code: "BANK_DETAILS_CHANGED", message: "invoice IBAN ...5566 differs from master record ...7890" }],
    po: { number: "PO-2026-0148", lines: [{ id: "1", desc: "Einrichtung Arbeitsplatzrechner", qty: "7", price: "140.00", received: "7" }] },
    history: [
      { number: "IT-26-0931", date: "2026-10-27", gross: "1487.50", gl: "4806" },
      { number: "IT-26-0874", date: "2026-09-28", gross: "1487.50", gl: "4806" },
    ],
    proposal: {
      action: "escalate", gl_account: "4806", citations: ["AP-bank-details"], reasons: [],
      explanation: "The IBAN on the invoice differs from the vendor master record. The change must be confirmed with the vendor through a known channel before payment, which a person does.",
      vendor_email_de: null,
    },
  },
  {
    id: 1017, received: "2026-11-01", format: "zugferd_pdf", status: "open", vendor: "DE100000032",
    fields: {
      seller_name: ["Muster Logistik GmbH", 1], seller_vat_id: ["DE100000032", 1],
      seller_address: [VENDORS.DE100000032.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE68200505504711000815", 1], number: ["ML-118204", 1],
      issue_date: ["2026-10-29", 1], delivery_date: ["2026-10-29", 1], due_date: ["2026-11-12", 1],
      po_number: ["PO-2026-0150", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["386.40", 1], vat_total: ["73.42", 1], gross_total: ["459.82", 1],
      amount_due: ["459.82", 1],
    },
    lines: [{ id: "1", item: "Paketversand national", qty: "46", price: "8.40", net: "386.40", rate: "19", ref: "1" }],
    kosit: true, gl: ["4910", 0.94], reasons: ["DUPLICATE_INVOICE"],
    failed: [{ code: "DUPLICATE_INVOICE", message: "invoice ML-118204 from DE100000032 was already received" }],
    po: { number: "PO-2026-0150", lines: [{ id: "1", desc: "Paketversand national", qty: "60", price: "8.40", received: "46" }] },
    history: [
      { number: "ML-118204", date: "2026-10-29", gross: "459.82", gl: "4910" },
      { number: "ML-117960", date: "2026-09-30", gross: "389.80", gl: "4910" },
    ],
    proposal: {
      action: "reject", gl_account: "4910", citations: ["AP-duplicates"], reasons: [],
      explanation: "Invoice ML-118204 from the same seller was already received on 2026-10-30 and booked; a duplicate is not booked.",
      vendor_email_de: null,
    },
  },
  {
    id: 1025, received: "2026-10-31", format: "scan", status: "open", vendor: "DE100000057",
    fields: {
      seller_name: ["Muster Haustechnik GmbH", 0.97], seller_vat_id: ["DE100000057", 0.91],
      seller_address: [VENDORS.DE100000057.address, 0.92], buyer_name: [BUYER.name, 0.95],
      iban: ["DE44500105175531007788", 0.93], number: ["HT-2026-081", 0.71],
      issue_date: ["2026-10-28", 0.95], delivery_date: ["2026-10-27", 0.92], due_date: ["2026-11-11", 0.91],
      po_number: ["PO-2026-0144", 0.93], buyer_reference: null,
      tax_exclusive_total: ["315.00", 0.94], vat_total: ["59.85", 0.62], gross_total: ["374.85", 0.96],
      amount_due: ["374.85", 0.95],
    },
    lines: [{ id: "1", item: "Austausch Thermostatventile", qty: "9", price: "35.00", net: "315.00", rate: "19", ref: "1" }],
    kosit: null, gl: ["4260", 0.91], reasons: ["LOW_EXTRACTION_CONFIDENCE"], failed: [],
    po: { number: "PO-2026-0144", lines: [{ id: "1", desc: "Thermostatventile tauschen", qty: "9", price: "35.00", received: "9" }] },
    history: [{ number: "HT-2026-077", date: "2026-10-21", gross: "761.60", gl: "4260" }],
    proposal: {
      action: "escalate", gl_account: "4260", citations: ["AP-automatic-booking"], reasons: [],
      explanation: "The scan was read with low confidence for required fields, so a person has to compare the fields with the page.",
      vendor_email_de: null,
    },
  },
  {
    id: 1024, received: "2026-11-02", format: "ubl", status: "open", vendor: "DE100000049",
    fields: {
      seller_name: ["Beispiel Kaffee KG", 1], seller_vat_id: ["DE100000049", 1],
      seller_address: [VENDORS.DE100000049.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE68370501981990123456", 1], number: ["2026-1203", 1],
      issue_date: ["2026-11-01", 1], delivery_date: ["2026-10-31", 1], due_date: ["2026-11-15", 1],
      po_number: ["PO-2026-0155", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["89.00", 1], vat_total: ["16.91", 1], gross_total: ["105.91", 1],
      amount_due: ["105.91", 1],
    },
    lines: [{ id: "1", item: "Kaffeevollautomat, Miete Oktober 2026", qty: "1", price: "89.00", net: "89.00", rate: "19", ref: "1" }],
    kosit: true, gl: ["4980", 0.58], reasons: ["LOW_GL_CONFIDENCE"], failed: [],
    po: { number: "PO-2026-0155", lines: [{ id: "1", desc: "Miete Kaffeevollautomat", qty: "1", price: "89.00", received: null }] },
    history: [{ number: "2026-1187", date: "2026-10-30", gross: "89.88", gl: "4650" }],
    proposal: {
      action: "approve_booking", gl_account: "4980", citations: ["AP-automatic-booking"], reasons: [],
      explanation: "All checks pass; only the account suggestion was below the threshold. The line is the monthly rent of a coffee machine, not coffee for guests, so 4980 (Betriebsbedarf) fits better than the vendor's usual 4650.",
      vendor_email_de: null,
    },
  },
  {
    id: 1031, received: "2026-11-02", format: "cii", status: "open", vendor: null,
    fields: {
      seller_name: ["Beispiel Beratung Nord GmbH", 1], seller_vat_id: ["DE100000073", 1],
      seller_address: [{ street: "Kontorhaus 1", postcode: "24103", city: "Kiel" }, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE68210501700012345678", 1], number: ["BBN-0042", 1],
      issue_date: ["2026-10-31", 1], delivery_date: ["2026-10-31", 1], due_date: ["2026-11-14", 1],
      po_number: null, buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["1800.00", 1], vat_total: ["342.00", 1], gross_total: ["2142.00", 1],
      amount_due: ["2142.00", 1],
    },
    lines: [{ id: "1", item: "Beratung Prozessanalyse, 12 Stunden", qty: "12", price: "150.00", net: "1800.00", rate: "19", ref: null }],
    kosit: true, gl: ["4950", 0.93], reasons: ["UNKNOWN_VENDOR", "NO_PO_REFERENCE"],
    failed: [
      { code: "UNKNOWN_VENDOR", message: "seller is not in the vendor master data" },
      { code: "NO_PO_REFERENCE", message: "invoice has no purchase order reference (BT-13)" },
    ],
    po: null, history: [],
    proposal: {
      action: "escalate", gl_account: null, citations: [], reasons: ["INSUFFICIENT_EVIDENCE"],
      explanation: "No rule text was found for this invoice; a person decides.",
      vendor_email_de: null,
    },
  },
  {
    id: 1013, received: "2026-11-03", format: "ubl", status: "open", vendor: "DE100000016",
    fields: {
      seller_name: ["Muster Bürobedarf GmbH", 1], seller_vat_id: ["DE100000016", 1],
      seller_address: [VENDORS.DE100000016.address, 1], buyer_name: [BUYER.name, 1],
      iban: ["DE89370400440532013000", 1], number: ["RE-2026-0433", 1],
      issue_date: ["2026-10-31", 1], delivery_date: ["2026-10-30", 1], due_date: ["2026-11-30", 1],
      po_number: ["PO-2026-0163", 1], buyer_reference: ["04011000-12345-34", 1],
      tax_exclusive_total: ["168.00", 1], vat_total: ["31.92", 1], gross_total: ["199.92", 1],
      amount_due: ["199.92", 1],
    },
    lines: [{ id: "1", item: "Kopierpapier A4, 500 Blatt", qty: "40", price: "4.20", net: "168.00", rate: "19", ref: "1" }],
    kosit: true, gl: ["4930", 0.97], reasons: ["QUANTITY_ABOVE_RECEIPT"],
    failed: [{ code: "QUANTITY_ABOVE_RECEIPT", message: "invoiced quantity above goods received: lines 1" }],
    po: { number: "PO-2026-0163", lines: [{ id: "1", desc: "Kopierpapier A4", qty: "40", price: "4.20", received: "30" }] },
    history: [
      { number: "RE-2026-0412", date: "2026-10-26", gross: "533.12", gl: "4930" },
      { number: "RE-2026-0377", date: "2026-08-12", gross: "249.90", gl: "4930" },
    ],
    proposal: null,
    // What "Ask assistant" returns in the prototype (POST /reviews/{id}/agent in A6b).
    askResult: {
      action: "request_correction", gl_account: "4930", citations: ["AP-goods-receipt"], reasons: [],
      explanation: "40 packs are invoiced but only 30 were received for PO-2026-0163; the invoice may not exceed the goods receipt.",
      vendor_email_de: email("RE-2026-0433", "31.10.2026", "Berechnet sind 40 Pakete Kopierpapier, geliefert wurden 30 Pakete."),
    },
  },
];

// The invoice that "Upload invoice" adds in the prototype.
const UPLOAD_SAMPLE = {
  id: 2006, received: TODAY, format: "zugferd_pdf", status: "auto_booked", vendor: "DE100000032",
  fields: {
    seller_name: ["Muster Logistik GmbH", 1], seller_vat_id: ["DE100000032", 1],
    seller_address: [VENDORS.DE100000032.address, 1], buyer_name: [BUYER.name, 1],
    iban: ["DE68200505504711000815", 1], number: ["ML-118377", 1],
    issue_date: ["2026-11-02", 1], delivery_date: ["2026-11-02", 1], due_date: ["2026-11-16", 1],
    po_number: ["PO-2026-0150", 1], buyer_reference: ["04011000-12345-34", 1],
    tax_exclusive_total: ["260.40", 1], vat_total: ["49.48", 1], gross_total: ["309.88", 1],
    amount_due: ["309.88", 1],
  },
  lines: [{ id: "1", item: "Paketversand national", qty: "31", price: "8.40", net: "260.40", rate: "19", ref: "1" }],
  kosit: true, gl: ["4910", 0.95], reasons: [], failed: [],
  po: { number: "PO-2026-0150", lines: [{ id: "1", desc: "Paketversand national", qty: "60", price: "8.40", received: "60" }] },
  history: [{ number: "ML-118204", date: "2026-10-29", gross: "459.82", gl: "4910" }],
  proposal: null,
};
