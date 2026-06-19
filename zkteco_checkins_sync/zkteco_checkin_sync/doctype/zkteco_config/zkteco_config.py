# Copyright (c) 2025

import frappe
from frappe.model.document import Document
from frappe import _
import requests
from frappe.utils import today, now_datetime, get_datetime
from datetime import timedelta
import json


class ZKTecoConfig(Document):
    pass


# =========================
# REGISTER TOKEN (PER DEVICE)
# =========================
@frappe.whitelist()
def register_api_token(docname):
    cfg = frappe.get_doc("ZKTeco Config", docname)

    if not all([cfg.server_ip, cfg.server_port, cfg.username, cfg.get_password("password")]):
        frappe.throw(_("Missing configuration"))

    url = f"http://{cfg.server_ip}:{cfg.server_port}/api-token-auth/"

    try:
        res = requests.post(url, json={
            "username": cfg.username,
            "password": cfg.get_password("password")
        }, timeout=15)

        if res.status_code != 200:
            frappe.throw(res.text)

        token = res.json().get("token")

        frappe.db.set_value("ZKTeco Config", docname, "token", token)
        frappe.db.commit()

        return {"success": True, "token": token}

    except Exception as e:
        frappe.throw(str(e))


# =========================
# TEST CONNECTION
# =========================
@frappe.whitelist()
def test_connection(docname):
    cfg = frappe.get_doc("ZKTeco Config", docname)

    if not cfg.token:
        return {"ok": False, "error": "Token missing"}

    url = f"http://{cfg.server_ip}:{cfg.server_port}/iclock/api/transactions/"

    try:
        res = requests.get(
            url,
            headers={"Authorization": f"Token {cfg.token}"},
            params={
                "start_time": f"{today()} 00:00:00",
                "end_time": f"{today()} 23:59:59"
            },
            timeout=15
        )

        if not res.ok:
            return {"ok": False, "error": res.text}

        data = res.json()
        txns = data.get("data") or data.get("results") or data or []

        return {"ok": True, "count": len(txns), "sample": txns[:5]}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# =========================
# FETCH DATA
# =========================
def fetch_zkteco_transactions(cfg, start, end):
    url = f"http://{cfg.server_ip}:{cfg.server_port}/iclock/api/transactions/"

    try:
        res = requests.get(
            url,
            headers={"Authorization": f"Token {cfg.token}"},
            params={
                "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end.strftime("%Y-%m-%d %H:%M:%S")
            },
            timeout=30
        )

        data = res.json()
        return data.get("data") or data.get("results") or data or []

    except Exception as e:
        frappe.log_error(str(e), "Fetch Error")
        return []


# =========================
# CREATE CHECKIN
# =========================
def create_employee_checkin(t):
    try:
        emp = t.get("emp_code")
        time = t.get("punch_time")

        if not emp or not time:
            return False

        employee = find_employee(emp)
        if not employee:
            return False

        time = get_datetime(time)
        device = t.get("terminal_alias") or t.get("terminal_sn")
        log_type = "OUT" if t.get("punch_state") == "1" else "IN"

        if frappe.db.exists("Employee Checkin", {
            "employee": employee,
            "time": time
        }):
            return True

        doc = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee,
            "time": time,
            "log_type": log_type,
            "device_id": device or "ZKTeco"
        })

        doc.insert(ignore_permissions=True)
        return True

    except Exception as e:
        frappe.log_error(str(e), "Checkin Error")
        return False


# =========================
# FIND EMPLOYEE
# =========================
def find_employee(code):
    return (
        frappe.db.get_value("Employee", {"employee": code}, "name") or
        frappe.db.get_value("Employee", {"user_id": code}, "name") or
        frappe.db.get_value("Employee", {"attendance_device_id": code}, "name")
    )


# =========================
# SYNC SINGLE DEVICE
# =========================
def sync_single_device(cfg):
    try:
        now = now_datetime()
        last = cfg.last_sync or (now - timedelta(days=1))
        last = get_datetime(last)

        txns = fetch_zkteco_transactions(cfg, last, now)

        count = 0
        for t in txns:
            if create_employee_checkin(t):
                count += 1

        frappe.db.set_value("ZKTeco Config", cfg.name, "last_sync", now)
        frappe.db.set_value(
            "ZKTeco Config",
            cfg.name,
            "total_synced_records",
            (cfg.total_synced_records or 0) + count
        )

    except Exception as e:
        frappe.log_error(str(e), f"Device Error {cfg.name}")


# =========================
# SYNC ALL DEVICES
# =========================
def sync_zkteco_transactions():
    configs = frappe.get_all("ZKTeco Config", fields=["name"])

    for c in configs:
        cfg = frappe.get_doc("ZKTeco Config", c.name)

        if not cfg.enable_sync or not cfg.token:
            continue

        sync_single_device(cfg)


# =========================
# MANUAL SYNC
# =========================
@frappe.whitelist()
def manual_sync(docname):
    cfg = frappe.get_doc("ZKTeco Config", docname)
    sync_single_device(cfg)
    return {"success": True}


# =========================
# SCHEDULER
# =========================
def scheduled_sync():
    try:
        configs = frappe.get_all("ZKTeco Config", fields=["name"])

        for c in configs:
            cfg = frappe.get_doc("ZKTeco Config", c.name)

            if not cfg.enable_sync:
                continue

            key = f"zkteco_{cfg.name}"
            last = frappe.cache().get_value(key)
            now = now_datetime()

            if last:
                diff = (now - get_datetime(last)).total_seconds()
                if diff < (cfg.seconds or 300):
                    continue

            frappe.cache().set_value(key, now)

            sync_single_device(cfg)

    except Exception as e:
        frappe.log_error(str(e), "Scheduler Error")


# =========================
# STATUS
# =========================
@frappe.whitelist()
def get_sync_status():
    configs = frappe.get_all("ZKTeco Config", fields=["name", "last_sync", "enable_sync"])

    return {
        "total_devices": len(configs),
        "devices": configs
    }