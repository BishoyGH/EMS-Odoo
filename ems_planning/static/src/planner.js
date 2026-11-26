import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

export class EmsPlanner extends Component {
    static template = "ems_planning.Planner";
    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = proxy({
            data: null,
            loading: true,
            start: false,
            weeks: 8,
            dragId: null,
            dragWeek: null,
            overKey: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("ems.allocation", "get_planner_data", [
            this.state.start || false,
            this.state.weeks,
        ]);
        this.state.start = this.state.data.start;
        this.state.loading = false;
    }

    shift(weeks) {
        const date = new Date(this.state.start + "T00:00:00");
        date.setDate(date.getDate() + weeks * 7);
        this.state.start = date.toISOString().slice(0, 10);
        return this.load();
    }

    today() {
        this.state.start = false;
        return this.load();
    }

    setWeeks(weeks) {
        this.state.weeks = weeks;
        return this.load();
    }

    chipStyle(chip) {
        const hue = (chip.color * 30) % 360;
        return `background: hsl(${hue} 60% 94%); border-left: 4px solid hsl(${hue} 55% 42%);`;
    }

    loadClass(cell) {
        if (cell.pct > 100) {
            return "o_ems_load_over";
        }
        if (cell.pct >= 80) {
            return "o_ems_load_high";
        }
        return cell.total ? "o_ems_load_ok" : "";
    }

    onDragStart(ev, chip, week) {
        this.state.dragId = chip.id;
        this.state.dragWeek = week;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(chip.id));
    }

    onDragEnd() {
        this.state.dragId = null;
        this.state.overKey = null;
    }

    onDragOver(ev, row, cell) {
        ev.preventDefault();
        this.state.overKey = `${row.id}-${cell.index}`;
    }

    async onDrop(ev, row, cell) {
        ev.preventDefault();
        const allocId = this.state.dragId;
        const fromWeek = this.state.dragWeek;
        this.state.dragId = null;
        this.state.overKey = null;
        if (!allocId) {
            return;
        }
        await this.orm.call("ems.allocation", "move_allocation", [allocId, row.id, cell.index - fromWeek]);
        await this.load();
    }

    openChip(chip) {
        this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ems.allocation",
                res_id: chip.id,
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.load() }
        );
    }

    addAllocation(row, cell) {
        const week = this.state.data.weeks[cell.index];
        this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ems.allocation",
                views: [[false, "form"]],
                target: "new",
                name: "New allocation",
                context: {
                    default_employee_id: row.id,
                    default_date_from: week.start,
                    default_date_to: week.end,
                    default_hours_per_day: 4,
                },
            },
            { onClose: () => this.load() }
        );
    }
}

registry.category("actions").add("ems_planner", EmsPlanner);
