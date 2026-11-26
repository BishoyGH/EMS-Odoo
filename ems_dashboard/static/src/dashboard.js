import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

export class EmsDashboard extends Component {
    static template = "ems_dashboard.Dashboard";
    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = proxy({ data: null, loading: true, error: null });
        onWillStart(() => this.load());
    }

    get kind() {
        const action = this.props.action;
        return (action.context && action.context.ems_dashboard_kind) || (action.params && action.params.kind);
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("ems.dashboard", "get_dashboard", [this.kind]);
            this.state.error = null;
        } catch (error) {
            this.state.error = (error.data && error.data.message) || error.message || String(error);
        }
        this.state.loading = false;
    }

    formatValue(value, fmt) {
        const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
        const money = (v) => {
            const cur = this.state.data.currency;
            const text = number.format(Math.round(v));
            return cur.position === "before" ? `${cur.symbol} ${text}` : `${text} ${cur.symbol}`;
        };
        switch (fmt) {
            case "money":
                return money(value);
            case "pct":
                return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)}%`;
            case "hours":
                return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)} h`;
            case "days":
                return `${Math.round(value)} d`;
            default:
                return number.format(value);
        }
    }

    openTile(tile) {
        if (tile.action) {
            this.actionService.doAction(tile.action);
        }
    }

    toneClass(tone) {
        return `o_ems_tone_${tone || "primary"}`;
    }

    async refresh() {
        await this.load();
    }
}

registry.category("actions").add("ems_dashboard", EmsDashboard);
