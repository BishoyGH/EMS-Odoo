import { registry } from "@web/core/registry";

function drag(fromSelector, toSelector) {
    const source = document.querySelector(fromSelector);
    const target = document.querySelector(toSelector);
    const dataTransfer = new DataTransfer();
    const fire = (el, type) =>
        el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer }));
    fire(source, "dragstart");
    fire(target, "dragover");
    fire(target, "drop");
    fire(source, "dragend");
}

registry.category("web_tour.tours").add("ems_planner_drag_tour", {
    steps: () => [
        {
            content: "Planner grid shows the bar of person A",
            trigger: ".o_ems_planner_grid .o_ems_chip[title*='Tour bar']",
        },
        {
            content: "Drag the bar to person B, one week later",
            trigger: ".o_ems_planner_grid",
            run: () => {
                const rows = [...document.querySelectorAll(".o_ems_planner_grid tbody tr")];
                const rowA = rows.find((r) => r.textContent.includes("Tour Person A"));
                const rowB = rows.find((r) => r.textContent.includes("Tour Person B"));
                rowA.id = "ems_row_a";
                rowB.id = "ems_row_b";
                drag("#ems_row_a .o_ems_chip", "#ems_row_b td:nth-of-type(2)");
            },
        },
        {
            content: "Bar now sits in person B's row",
            trigger: ".o_ems_planner_grid tbody tr:contains('Tour Person B') .o_ems_chip",
        },
        {
            content: "Person A no longer has it",
            trigger: ".o_ems_planner_grid tbody tr:contains('Tour Person A'):not(:has(.o_ems_chip))",
        },
    ],
});
