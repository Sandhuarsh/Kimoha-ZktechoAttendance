// Copyright (c) 2025

frappe.ui.form.on("ZKTeco Config", {

    refresh(frm) {
        // Buttons only if token + enabled
        if (frm.doc.enable_sync && frm.doc.token) {
            frm.add_custom_button(__('Manual Sync'), function () {
                manual_sync(frm);
            }, __('Actions'));

            frm.add_custom_button(__('Sync Status'), function () {
                show_sync_status(frm);
            }, __('Actions'));
        }

        if (frm.doc.enable_sync) {
            show_sync_indicator(frm);
        }
    },

    enable_sync(frm) {
        if (frm.doc.enable_sync) {
            frappe.show_alert({
                message: __('ZKTeco sync enabled. Configure and test connection.'),
                indicator: 'blue'
            });
        }
    },

    // =========================
    // TEST CONNECTION (FIXED)
    // =========================
    test_connection(frm) {
        frappe.call({
            method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.test_connection",
            args: {
                docname: frm.doc.name   // ✅ IMPORTANT
            },
            freeze: true,
            freeze_message: __("Testing connection...")
        }).then((r) => {

            const msg = r.message || {};

            if (msg.ok) {
                frappe.show_alert({
                    message: __(`✅ Connected! Transactions: ${msg.count || 0}`),
                    indicator: "green"
                });

                if (msg.sample && msg.sample.length) {
                    show_transaction_preview(msg.sample, msg.count);
                }

            } else {
                frappe.msgprint({
                    title: __("Connection Failed"),
                    message: msg.error || "Unknown error",
                    indicator: "red"
                });
            }

        });
    },

    // =========================
    // REGISTER TOKEN (FIXED)
    // =========================
    register_api_token(frm) {
        frappe.call({
            method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.register_api_token",
            args: {
                docname: frm.doc.name   // ✅ IMPORTANT
            },
            freeze: true,
            freeze_message: __("Registering token...")
        }).then((r) => {

            if (r.message && r.message.token) {
                frm.set_value("token", r.message.token);

                frm.save().then(() => {
                    frappe.show_alert({
                        message: __("✅ Token saved successfully"),
                        indicator: "green"
                    });
                });
            }

        });
    }
});


// =========================
// TRANSACTION PREVIEW
// =========================
function show_transaction_preview(transactions, total_count) {

    let html = `<b>Transactions Found: ${total_count}</b><br><br>`;

    html += `<table class="table table-bordered">
        <tr>
            <th>Emp Code</th>
            <th>Time</th>
        </tr>`;

    transactions.forEach(t => {
        html += `<tr>
            <td>${t.emp_code || "-"}</td>
            <td>${t.punch_time || "-"}</td>
        </tr>`;
    });

    html += `</table>`;

    frappe.msgprint({
        title: "Preview",
        message: html,
        wide: true
    });
}


// =========================
// MANUAL SYNC (PER DEVICE)
// =========================
function manual_sync(frm) {
    frappe.call({
        method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.manual_sync",
        args: {
            docname: frm.doc.name   // ✅ IMPORTANT
        },
        freeze: true,
        freeze_message: __("Syncing...")
    }).then((r) => {

        if (r.message && r.message.success) {
            frappe.show_alert({
                message: "✅ Sync Completed",
                indicator: "green"
            });
        }
    });
}


// =========================
// STATUS (MULTI DEVICE)
// =========================
function show_sync_status(frm) {
    frappe.call({
        method: "zkteco_checkins_sync.zkteco_checkin_sync.doctype.zkteco_config.zkteco_config.get_sync_status"
    }).then((r) => {

        let html = "<b>Total Devices: " + r.message.total_devices + "</b><br><br>";

        r.message.devices.forEach(d => {
            html += `<div style="margin-bottom:10px;">
                        <b>${d.name}</b><br>
                        Enabled: ${d.enable_sync ? "✅" : "❌"}<br>
                        Last Sync: ${d.last_sync || "Never"}
                     </div><hr>`;
        });

        frappe.msgprint({
            title: "Sync Status",
            message: html
        });
    });
}


// =========================
// INDICATOR
// =========================
function show_sync_indicator(frm) {

    let color = "red";
    let text = "Sync Disabled";

    if (frm.doc.enable_sync && frm.doc.token) {
        color = "green";
        text = `Active (${frm.doc.seconds}s)`;
    } else if (frm.doc.enable_sync) {
        color = "orange";
        text = "Token Missing";
    }

    frm.dashboard.add_indicator(text, color);
}