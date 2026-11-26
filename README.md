# EMS Odoo ERP (Odoo 20)

Odoo 20 addons that rebuild the EMS desktop register (`EMS_PO_Register.exe`) and cover the workflow in the EMS functional specification. Written against the Odoo 20.0 Community source. It installs cleanly with demo data and the included tests pass.

## Modules

| Module | Odoo app menu | What it does | Depends on |
|---|---|---|---|
| `ems_base` | (shared) | Security groups, partner and project extensions, project code sequence | contacts, project, account |
| `ems_proposals` | EMS Proposals | Proposal numbers (`Pyynnn`), revisions, follow-ups, lead to project link, stages, lost reasons, bid client stats | ems_base, crm |
| `ems_register` | EMS Register | Purchase orders with Letter of Appointment: LOA numbering, payment milestones, conditions, standard clauses, sub-budget check on confirm, LOA PDF | ems_base, purchase |
| `ems_payments` | EMS Payments | Fee stages (invoice a stage only when the trigger evidence is ticked), client invoice follow-ups, overdue cron, customer statement PDF | ems_base, account |
| `ems_services` | EMS Services | Services and cost codes (`project-code-sub-code`), milestones on `project.milestone`, service catalogue | ems_base, project, product |
| `ems_planning` | EMS Planning | Allocations, calendar and pivot planner, weekly plan PDF, utilisation, project cost | ems_people, ems_services |
| `ems_people` | EMS People | Grades and rates, employee extensions, offer letters (PDF), onboarding tasks, roles | ems_base, hr, hr_holidays |
| `ems_finance` | (Sales, Projects, Purchase) | Award flow (sales order baseline, analytic account, P0-P7 WBS template), variations with signed approval, timesheets with cost snapshot and lock, PO vs bill no-double-count, Office Overhead, EAC/margin and AR aging reports, profit snapshots | all v1 apps, sale_management, hr_timesheet |
| `ems_migration` | EMS Data Migration | Re-runnable import of the legacy `.dat` backup (17 tables), data-issues report, 5 Excel import templates with data dictionary | ems_finance |
| `ems_dashboard` | EMS Dashboards | One OWL client action rendering 8 dashboards (register, payments, proposals, portfolio, resource, economics, finance, audit) | ems_finance |
| `ems_erp` | | Meta module. Installing it installs all of the above, and it holds the integration tests | all |

## Install

Requires Odoo 20.0 (Python 3.12+, PostgreSQL 16+).

```bash
odoo-bin --addons-path=/path/to/odoo/addons,/path/to/ems-odoo -d ems -i ems_erp --stop-after-init
# with demo data and tests:
odoo-bin --addons-path=... -d ems_test -i ems_erp --with-demo --test-enable --test-tags /ems_erp --stop-after-init
```

Install a single area with its module name (for example `-i ems_register`); dependencies come with it.

## Security

Groups (in `ems_base`, under the "EMS" privilege): **User** (read and work on records), **Manager** (create, confirm, delete), **Rates Manager** and **Administrator**. Internal cost rates, salary packages and bank/IBAN/MOL fields use `groups="ems_base.group_ems_rates"` on the field. This replaces the exe's password vault. Access rights use Odoo 20's `ir.access.csv` format.

## Demo data

The pilot project from the pilot data workbook: SOL Properties, Sheikh Zayed Road Tower (award AED 125,000 ex VAT, proposal AED 245,000 kept as history), fee stages 25/50/25, tracker resource plan, and sample grades, employees, a vendor PO and an offer. Cost rates are deliberately left empty because the tracker rates are charge-out rates and no cost ledger exists. Data-quality flags from the workbook (RFP date, 120% engagement) are noted on the records, not silently fixed.

## Approval matrix and audit trail

`ems_base` provides an approval matrix (`ems.approval.rule`) with gates for bid, proposal, baseline, PO, variation, timesheet, invoice and closure; rules enforce groups and block self-approval. Watched fields on projects, fee stages, grades, employees, milestones, tasks, POs, timesheets and sales orders are logged to the audit trail via `ems.audit.mixin`. Documents are attached by category through `ems.document` tabs.

## Migrating the legacy `.dat`

Open EMS Data Migration, choose the backup file and run. The import is idempotent (external ids `__import__.ems_<table>_<id>`), rows that fail become data issues instead of aborting, and a report lists suspect data (projects without proposals, won with zero award, duplicate leads, fee stages not 100%). Never commit the `.dat` (it is git-ignored).

## Planner

The Planner menu is a drag-and-drop grid of people by weeks; dragging a bar moves it to another person or week. Hours use the employee working calendar, public holidays and leave.

## Remaining gaps

- PO/LOA, offer, weekly plan and statement PDFs are QWeb layouts with a shared look, not pixel-matched to the exe.
- No multi-company record rules (single company assumed).
- Cost rates are not migrated (the backup holds charge-out rates only); enter them under Grades.
- Proposal folder-template creation on disk is not implemented; documents are stored in Odoo.
- Enterprise features (Gantt, Spreadsheet dashboards) are not used.
