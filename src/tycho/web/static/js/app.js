/* Tycho Dashboard JS */

// Select-all checkbox handler
document.addEventListener("DOMContentLoaded", function () {
    const selectAll = document.getElementById("select-all");
    if (selectAll) {
        selectAll.addEventListener("change", function () {
            document.querySelectorAll(".job-checkbox").forEach(function (cb) {
                cb.checked = selectAll.checked;
            });
        });
    }
});

// Re-bind select-all after HTMX swaps
document.addEventListener("htmx:afterSwap", function () {
    const selectAll = document.getElementById("select-all");
    if (selectAll) {
        selectAll.addEventListener("change", function () {
            document.querySelectorAll(".job-checkbox").forEach(function (cb) {
                cb.checked = selectAll.checked;
            });
        });
    }
});
