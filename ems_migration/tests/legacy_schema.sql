CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE res_partner (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    company_type  TEXT NOT NULL DEFAULT 'company',
    x_category    TEXT,
    ref           TEXT,
    vat           TEXT,
    country_code  TEXT,
    email         TEXT,
    phone         TEXT,
    mobile        TEXT,
    website       TEXT,
    street        TEXT,
    street2       TEXT,
    city          TEXT,
    zip           TEXT,
    function      TEXT,
    x_bank        TEXT,
    supplier_rank INTEGER NOT NULL DEFAULT 1,
    customer_rank INTEGER NOT NULL DEFAULT 0,
    comment       TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    create_date   TEXT,
    write_date    TEXT
, image_1920 BLOB, x_is_end_client INTEGER NOT NULL DEFAULT 0, x_is_consultant INTEGER NOT NULL DEFAULT 0, x_sector TEXT, x_licence_no TEXT, x_licence_expiry TEXT, x_contact_name TEXT, x_contact_email TEXT, x_contact_phone TEXT, x_client_payment_days INTEGER, x_profile TEXT);
CREATE TABLE project_project (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    x_code             TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    partner_id         INTEGER REFERENCES res_partner(id),
    user_id            TEXT,
    x_contract_ref     TEXT,
    currency_id        TEXT NOT NULL DEFAULT 'AED',
    x_contract_value   REAL NOT NULL DEFAULT 0,
    x_delivery_budget  REAL NOT NULL DEFAULT 0,
    x_sub_budget       REAL NOT NULL DEFAULT 0,
    date_start         TEXT,
    date               TEXT,
    stage              TEXT NOT NULL DEFAULT 'In Progress',
    tag_ids            TEXT,
    description        TEXT,
    active             INTEGER NOT NULL DEFAULT 1,
    create_date        TEXT,
    write_date         TEXT
, x_end_client_id INTEGER REFERENCES res_partner(id), x_consultant_id INTEGER REFERENCES res_partner(id), x_authority TEXT, x_authority_ref TEXT, x_variation_value REAL NOT NULL DEFAULT 0, x_account_manager TEXT, x_client_po TEXT, x_service TEXT, x_proposal_id INTEGER REFERENCES crm_lead(id) ON DELETE SET NULL);
CREATE TABLE purchase_order (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL UNIQUE,
    partner_ref          TEXT,
    x_quotation_ref      TEXT,
    x_quotation_date     TEXT,
    x_tax_treatment      TEXT NOT NULL DEFAULT 'uae5',
    x_exclusions         TEXT,
    partner_id           INTEGER NOT NULL REFERENCES res_partner(id),
    project_id           INTEGER REFERENCES project_project(id),
    date_order           TEXT,
    date_approve         TEXT,
    date_planned         TEXT,
    state                TEXT NOT NULL DEFAULT 'draft',
    currency_id          TEXT NOT NULL DEFAULT 'AED',
    amount_untaxed       REAL NOT NULL DEFAULT 0,
    amount_tax           REAL NOT NULL DEFAULT 0,
    amount_total         REAL NOT NULL DEFAULT 0,
    origin               TEXT,
    user_id              TEXT,
    payment_term         TEXT,
    notes                TEXT,
    x_loa_ref            TEXT,
    x_loa_revision       TEXT NOT NULL DEFAULT 'R0',
    x_loa_date           TEXT,
    x_signed_by          TEXT,
    x_date_start         TEXT,
    x_completion_basis   TEXT NOT NULL DEFAULT 'duration',
    x_duration           REAL NOT NULL DEFAULT 0,
    x_duration_unit      TEXT NOT NULL DEFAULT 'calendar days',
    x_payment_days       INTEGER NOT NULL DEFAULT 30,
    x_scope              TEXT,
    x_deliverables       TEXT,
    x_document_location  TEXT,
    x_follow_up_date     TEXT,
    x_next_action        TEXT,
    x_print_count        INTEGER NOT NULL DEFAULT 0,
    create_date          TEXT,
    write_date           TEXT
, x_payment_terms TEXT, x_advance_pct REAL NOT NULL DEFAULT 0, x_retention_pct REAL NOT NULL DEFAULT 0, x_retention_release TEXT, x_governing_law TEXT, x_forum TEXT, x_liability_cap TEXT, x_insurance TEXT, x_delay_damages TEXT, x_notice_days INTEGER NOT NULL DEFAULT 14, x_cure_days INTEGER NOT NULL DEFAULT 14, x_restriction_months INTEGER NOT NULL DEFAULT 12, x_review_days INTEGER NOT NULL DEFAULT 10, x_ems_rep TEXT, x_notice_email TEXT, x_terms TEXT, x_special_conditions TEXT, x_po_seq INTEGER, x_loa_seq INTEGER, x_signed INTEGER NOT NULL DEFAULT 1);
CREATE TABLE purchase_order_line (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL REFERENCES purchase_order(id) ON DELETE CASCADE,
    sequence       INTEGER NOT NULL DEFAULT 10,
    name           TEXT NOT NULL,
    product_qty    REAL NOT NULL DEFAULT 1,
    product_uom    TEXT NOT NULL DEFAULT 'Lump sum',
    price_unit     REAL NOT NULL DEFAULT 0,
    x_tax_rate     REAL NOT NULL DEFAULT 5,
    price_subtotal REAL NOT NULL DEFAULT 0,
    price_tax      REAL NOT NULL DEFAULT 0,
    price_total    REAL NOT NULL DEFAULT 0
);
CREATE TABLE account_move (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT,
    ref               TEXT,
    move_type         TEXT NOT NULL DEFAULT 'in_invoice',
    partner_id        INTEGER REFERENCES res_partner(id),
    purchase_id       INTEGER REFERENCES purchase_order(id) ON DELETE SET NULL,
    invoice_date      TEXT,
    invoice_date_due  TEXT,
    currency_id       TEXT NOT NULL DEFAULT 'AED',
    x_description     TEXT,
    amount_untaxed    REAL NOT NULL DEFAULT 0,
    amount_tax        REAL NOT NULL DEFAULT 0,
    amount_total      REAL NOT NULL DEFAULT 0,
    x_amount_paid     REAL NOT NULL DEFAULT 0,
    x_payment_date    TEXT,
    payment_state     TEXT NOT NULL DEFAULT 'not_paid',
    state             TEXT NOT NULL DEFAULT 'draft',
    narration         TEXT,
    create_date       TEXT,
    write_date        TEXT
);
CREATE TABLE mail_message (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    model    TEXT NOT NULL,
    res_id   INTEGER NOT NULL,
    date     TEXT NOT NULL,
    kind     TEXT NOT NULL DEFAULT 'notification',
    body     TEXT NOT NULL,
    author   TEXT
);
CREATE TABLE purchase_payment_milestone (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  INTEGER NOT NULL REFERENCES purchase_order(id) ON DELETE CASCADE,
    sequence  INTEGER NOT NULL DEFAULT 10,
    name      TEXT NOT NULL,
    percent   REAL NOT NULL DEFAULT 0,
    amount    REAL NOT NULL DEFAULT 0,
    due_on    TEXT
, line_id INTEGER REFERENCES purchase_order_line(id) ON DELETE SET NULL);
CREATE TABLE ir_attachment (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    res_model    TEXT NOT NULL,
    res_id       INTEGER NOT NULL,
    name         TEXT NOT NULL,
    x_category   TEXT,
    description  TEXT,
    mimetype     TEXT,
    file_size    INTEGER NOT NULL DEFAULT 0,
    store_fname  TEXT,                 -- path (relative to the Attachments folder) when stored on disk
    datas        BLOB,                 -- file content when stored inside the database
    checksum     TEXT,
    create_date  TEXT,
    create_uid   TEXT
);
CREATE TABLE x_fee_stage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES project_project(id) ON DELETE CASCADE,
    sequence    INTEGER NOT NULL DEFAULT 10,
    phase       TEXT,                 -- heading the stage belongs to, e.g. Phase 1 / Concept stage
    name        TEXT NOT NULL,
    percent     REAL NOT NULL DEFAULT 0,
    basis       REAL NOT NULL DEFAULT 0,   -- amount the percentage applies to (phase value); 0 = project contract
    amount      REAL NOT NULL DEFAULT 0,   -- excl. VAT
    progress    REAL NOT NULL DEFAULT 0,   -- % of the stage completed
    create_date TEXT,
    write_date  TEXT
);
CREATE TABLE x_client_invoice (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES project_project(id),
    stage_id            INTEGER REFERENCES x_fee_stage(id) ON DELETE SET NULL,
    partner_id          INTEGER REFERENCES res_partner(id),
    name                TEXT,                 -- invoice number
    ref                 TEXT,                 -- reference / description printed on the invoice
    invoice_date        TEXT,
    invoice_date_due    TEXT,
    currency_id         TEXT NOT NULL DEFAULT 'AED',
    amount_untaxed      REAL NOT NULL DEFAULT 0,
    amount_tax          REAL NOT NULL DEFAULT 0,
    amount_total        REAL NOT NULL DEFAULT 0,
    x_amount_paid       REAL NOT NULL DEFAULT 0,
    x_payment_date      TEXT,
    payment_state       TEXT NOT NULL DEFAULT 'not_paid',
    state               TEXT NOT NULL DEFAULT 'posted',
    x_follow_up_date    TEXT,
    x_follow_up_method  TEXT,
    x_follow_up_notes   TEXT,
    x_client_response   TEXT,
    x_next_follow_up    TEXT,
    x_next_method       TEXT,
    narration           TEXT,
    create_date         TEXT,
    write_date          TEXT
);
CREATE TABLE crm_lead (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    x_number           TEXT UNIQUE,                 -- P26467
    x_seq              INTEGER,                     -- 467: running number of the category
    x_category         TEXT NOT NULL DEFAULT '3rd Party',
    name               TEXT NOT NULL,               -- project name
    x_project_code     TEXT,                        -- short code used in the folder name, e.g. TWT
    partner_id         INTEGER REFERENCES res_partner(id),
    x_client_code      TEXT,                        -- client abbreviation in the folder name, e.g. AHS
    x_contact_name     TEXT,
    x_contact_email    TEXT,
    x_contact_phone    TEXT,
    x_end_client       TEXT,                        -- developer / owner when the client is a consultant or contractor
    x_scope            TEXT,                        -- 3RD PARTY STR …
    x_discipline       TEXT,                        -- STR / GEO / STR&GEO / VE in the folder name
    x_location         TEXT,
    x_location_code    TEXT,                        -- DXB …
    stage              TEXT NOT NULL DEFAULT 'rfp',
    currency_id        TEXT NOT NULL DEFAULT 'AED',
    expected_revenue   REAL NOT NULL DEFAULT 0,     -- fee of the latest revision (Odoo expected_revenue)
    x_first_fee        REAL NOT NULL DEFAULT 0,     -- fee of the first submission
    x_revision         INTEGER NOT NULL DEFAULT 0,  -- latest revision number
    x_awarded_value    REAL NOT NULL DEFAULT 0,     -- value secured (awarded fee or the project's contract value)
    date_open          TEXT,                        -- RFP received
    date_deadline      TEXT,                        -- submission due
    x_date_submitted   TEXT,                        -- first submission (R0)
    x_date_last_rev    TEXT,                        -- latest revision
    date_closed        TEXT,                        -- awarded / lost / cancelled on
    x_register_code    TEXT,                        -- register project code(s) (yy-nnnn) noted before the project exists in the register
    user_id            TEXT,                        -- prepared by
    x_lost_reason      TEXT,
    x_competitor       TEXT,
    x_competitor_fee   REAL NOT NULL DEFAULT 0,
    x_follow_up_date   TEXT,
    x_follow_up_method TEXT,
    x_client_response  TEXT,
    x_next_follow_up   TEXT,
    x_next_method      TEXT,
    x_folder           TEXT,                        -- full path of the proposal folder
    x_proposal_file    TEXT,                        -- proposal document created from the template
    description        TEXT,                        -- project understanding / remarks
    x_source           TEXT,                        -- imported from (workbook row)
    active             INTEGER NOT NULL DEFAULT 1,
    create_date        TEXT,
    write_date         TEXT
);
CREATE TABLE crm_lead_revision (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id     INTEGER NOT NULL REFERENCES crm_lead(id) ON DELETE CASCADE,
    revision    INTEGER NOT NULL DEFAULT 0,
    date        TEXT,
    amount      REAL NOT NULL DEFAULT 0,
    note        TEXT,
    create_date TEXT,
    write_date  TEXT
);
CREATE TABLE x_grade (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,          -- e.g. G1 / SE / PE
    name        TEXT NOT NULL,                 -- e.g. Senior Engineer
    sequence    INTEGER NOT NULL DEFAULT 10,
    create_date TEXT,
    write_date  TEXT
);
CREATE TABLE hr_employee (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    x_code          TEXT,                      -- staff number
    job_title       TEXT,
    grade_id        INTEGER REFERENCES x_grade(id) ON DELETE SET NULL,
    department      TEXT,
    employment_type TEXT NOT NULL DEFAULT 'Full-time',
    work_email      TEXT,
    mobile_phone    TEXT,
    x_hours_week    REAL NOT NULL DEFAULT 40,  -- capacity
    x_plannable     INTEGER NOT NULL DEFAULT 1,-- shown in the planner
    date_start      TEXT,                      -- joined
    date_end        TEXT,                      -- left
    x_manager       TEXT,
    notes           TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    create_date     TEXT,
    write_date      TEXT
);
CREATE TABLE hr_leave (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER REFERENCES hr_employee(id) ON DELETE CASCADE,   -- NULL = public holiday for everyone
    kind        TEXT NOT NULL DEFAULT 'Annual leave',
    date_from   TEXT NOT NULL,
    date_to     TEXT NOT NULL,
    name        TEXT,
    create_date TEXT,
    write_date  TEXT
);
CREATE TABLE x_project_service (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES project_project(id) ON DELETE CASCADE,
    sequence     INTEGER NOT NULL DEFAULT 10,
    x_code       TEXT,                         -- sub-code: cost code = project code + '-' + sub-code
    name         TEXT NOT NULL,
    discipline   TEXT,
    fee          REAL NOT NULL DEFAULT 0,      -- fee of the service excl. VAT (0 = the project contract total when it is the only service)
    budget_hours REAL NOT NULL DEFAULT 0,
    manager_id   INTEGER REFERENCES hr_employee(id) ON DELETE SET NULL,
    state        TEXT NOT NULL DEFAULT 'active',
    date_start   TEXT,
    date_end     TEXT,
    notes        TEXT,
    create_date  TEXT,
    write_date   TEXT
, item_id INTEGER REFERENCES x_service_item(id) ON DELETE SET NULL);
CREATE TABLE x_project_milestone (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES project_project(id) ON DELETE CASCADE,
    service_id    INTEGER REFERENCES x_project_service(id) ON DELETE SET NULL,
    stage_id      INTEGER REFERENCES x_fee_stage(id) ON DELETE SET NULL,   -- fee stage invoiced when the milestone is reached
    sequence      INTEGER NOT NULL DEFAULT 10,
    name          TEXT NOT NULL,
    date_start    TEXT,
    date_deadline TEXT,
    budget_hours  REAL NOT NULL DEFAULT 0,
    owner_id      INTEGER REFERENCES hr_employee(id) ON DELETE SET NULL,
    state         TEXT NOT NULL DEFAULT 'todo',
    progress      REAL NOT NULL DEFAULT 0,
    date_done     TEXT,
    description   TEXT,
    create_date   TEXT,
    write_date    TEXT
, item_id INTEGER REFERENCES x_service_item(id) ON DELETE SET NULL);
CREATE TABLE x_allocation (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id   INTEGER NOT NULL REFERENCES hr_employee(id) ON DELETE CASCADE,
    project_id    INTEGER REFERENCES project_project(id) ON DELETE CASCADE,   -- NULL = internal / non-project time
    service_id    INTEGER REFERENCES x_project_service(id) ON DELETE SET NULL,
    milestone_id  INTEGER REFERENCES x_project_milestone(id) ON DELETE SET NULL,
    date_from     TEXT NOT NULL,
    date_to       TEXT NOT NULL,
    hours_per_day REAL NOT NULL DEFAULT 8,
    name          TEXT,                         -- the action / task: printed on the weekly action plan
    x_tentative   INTEGER NOT NULL DEFAULT 0,   -- pencilled in, not confirmed
    create_date   TEXT,
    write_date    TEXT
);
CREATE TABLE x_hr_role (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    department      TEXT,
    summary         TEXT,
    responsibilities TEXT,
    qualifications  TEXT,
    sequence        INTEGER DEFAULT 10,
    active          INTEGER DEFAULT 1,
    create_date     TEXT,
    write_date      TEXT
);
CREATE TABLE x_offer (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT,
    x_seq           INTEGER,
    x_revision      INTEGER DEFAULT 0,
    state           TEXT DEFAULT 'draft',
    country         TEXT DEFAULT 'UAE',
    candidate       TEXT NOT NULL,
    title           TEXT DEFAULT 'Mr.',
    nationality     TEXT,
    email           TEXT,
    phone           TEXT,
    role_id         INTEGER REFERENCES x_hr_role(id) ON DELETE SET NULL,
    position        TEXT,
    department      TEXT,
    grade_id        INTEGER REFERENCES x_grade(id) ON DELETE SET NULL,
    reports_to      TEXT,
    work_location   TEXT,
    date_offer      TEXT,
    date_start      TEXT,
    valid_days      INTEGER DEFAULT 2,
    contract_type   TEXT DEFAULT 'fixed',
    contract_months INTEGER DEFAULT 24,
    currency        TEXT DEFAULT 'AED',
    salary_basis    TEXT DEFAULT 'gross',
    basic           REAL DEFAULT 0,
    housing         REAL DEFAULT 0,
    transport       REAL DEFAULT 0,
    other           REAL DEFAULT 0,
    other_label     TEXT,
    probation_months INTEGER DEFAULT 6,
    notice_text     TEXT,
    hours_text      TEXT,
    leave_text      TEXT,
    benefits_text   TEXT,
    air_ticket      INTEGER DEFAULT 0,
    non_compete_months INTEGER DEFAULT 0,
    special_terms   TEXT,
    job_summary     TEXT,
    job_duties      TEXT,
    job_quals       TEXT,
    signatory       TEXT,
    signatory_title TEXT,
    employee_id     INTEGER REFERENCES hr_employee(id) ON DELETE SET NULL,
    date_sent       TEXT,
    date_decided    TEXT,
    notes           TEXT,
    create_date     TEXT,
    write_date      TEXT
);
CREATE TABLE x_onboarding (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES hr_employee(id) ON DELETE CASCADE,
    offer_id        INTEGER REFERENCES x_offer(id) ON DELETE SET NULL,
    sequence        INTEGER DEFAULT 10,
    name            TEXT NOT NULL,
    owner           TEXT,
    date_due        TEXT,
    done            INTEGER DEFAULT 0,
    date_done       TEXT,
    note            TEXT,
    create_date     TEXT,
    write_date      TEXT
);
CREATE TABLE x_service_item (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'service',
    discipline  TEXT,
    uom         TEXT,
    unit_price  REAL,
    currency_id TEXT,
    description TEXT,
    sequence    INTEGER NOT NULL DEFAULT 100,
    active      INTEGER NOT NULL DEFAULT 1,
    create_date TEXT,
    write_date  TEXT
);
