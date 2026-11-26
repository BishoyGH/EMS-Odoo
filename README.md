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

## Known gaps (not in v1)

- **Planner** is a calendar and pivot, not a drag-and-drop grid. Odoo Community has no Gantt view. The custom OWL grid is the next step (Enterprise Planning replaces it).
- Dashboards are graph/pivot views. No custom OWL or Spreadsheet dashboards yet.
- PO and LOA PDFs are functional QWeb layouts, not yet pixel-matched to the exe printouts. No Word export for offers.
- Allocation days count Monday to Friday and ignore public holidays and leave.
- No migration script for the `.dat` backup, and Phase 2 items from the spec (timesheet cost snapshots, variation approvals, analytic P&L, approval matrix).
- No record rules (single company assumed).
