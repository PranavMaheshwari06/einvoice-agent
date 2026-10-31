-- Master data, invoices and everything the pipeline stores about them.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vendors (
    vat_id text PRIMARY KEY,
    name   text NOT NULL,
    iban   text NOT NULL
);

CREATE TABLE purchase_orders (
    po_number      text PRIMARY KEY,
    vendor_vat_id  text NOT NULL REFERENCES vendors (vat_id)
);

CREATE TABLE po_lines (
    po_number   text NOT NULL REFERENCES purchase_orders (po_number),
    line_id     text NOT NULL,
    description text NOT NULL,
    quantity    numeric(14, 4) NOT NULL,
    unit_price  numeric(14, 4) NOT NULL,
    PRIMARY KEY (po_number, line_id)
);

CREATE TABLE goods_receipts (
    id          bigserial PRIMARY KEY,
    po_number   text NOT NULL,
    line_id     text NOT NULL,
    quantity    numeric(14, 4) NOT NULL,
    received_on date NOT NULL,
    FOREIGN KEY (po_number, line_id) REFERENCES po_lines (po_number, line_id)
);

CREATE TABLE invoices (
    id             bigserial PRIMARY KEY,
    format         text NOT NULL,
    seller_vat_id  text,
    invoice_number text,
    gross_total    numeric(14, 2),
    issue_date     date,
    source_file    text NOT NULL,
    canonical      jsonb NOT NULL,
    received_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (seller_vat_id, invoice_number)
);

CREATE TABLE checks (
    id         bigserial PRIMARY KEY,
    invoice_id bigint NOT NULL REFERENCES invoices (id),
    code       text NOT NULL,
    passed     boolean NOT NULL,
    severity   text NOT NULL,
    message    text NOT NULL
);

CREATE TABLE decisions (
    invoice_id bigint PRIMARY KEY REFERENCES invoices (id),
    kind       text NOT NULL CHECK (kind IN ('AUTO_BOOK', 'REVIEW')),
    reasons    text[] NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE proposals (
    id              bigserial PRIMARY KEY,
    invoice_id      bigint NOT NULL REFERENCES invoices (id),
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'corrected', 'rejected')),
    action          text NOT NULL,
    gl_account      text,
    explanation     text NOT NULL,
    citations       text[] NOT NULL,
    vendor_email_de text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bookings (
    id          bigserial PRIMARY KEY,
    invoice_id  bigint NOT NULL UNIQUE REFERENCES invoices (id),
    proposal_id bigint REFERENCES proposals (id),
    gl_account  text NOT NULL,
    net_total   numeric(14, 2) NOT NULL,
    vat_total   numeric(14, 2) NOT NULL,
    gross_total numeric(14, 2) NOT NULL,
    due_date    date,
    booked_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE corrections (
    id          bigserial PRIMARY KEY,
    proposal_id bigint NOT NULL REFERENCES proposals (id),
    field       text NOT NULL,
    old_value   text,
    new_value   text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rule_chunks (
    source_id text PRIMARY KEY,
    title     text NOT NULL,
    body      text NOT NULL,
    embedding vector(384) NOT NULL
);

CREATE TABLE drift_runs (
    id      bigserial PRIMARY KEY,
    run_at  timestamptz NOT NULL DEFAULT now(),
    metric  text NOT NULL,
    value   double precision NOT NULL,
    flagged boolean NOT NULL
);
