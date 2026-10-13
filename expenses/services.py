from audit.services import log as audit_log
from businesses.db import atomic


@atomic
def create_report(form, formset, user, request=None):
    report = form.save(commit=False)
    report.created_by = user
    report.save()
    formset.instance = report
    formset.save()
    audit_log(user, "expense_report_created", report,
              changes={"lines": report.lines.count(), "total": str(report.total)}, request=request)
    return report


@atomic
def update_report(form, formset, user, request=None):
    report = form.save()
    formset.instance = report
    formset.save()
    changes = {
        "fields": list(form.changed_data),
        "lines_changed": len(formset.changed_objects),
        "lines_added": len(formset.new_objects),
        "lines_removed": len(formset.deleted_objects),
        "total": str(report.total),
    }
    audit_log(user, "expense_report_updated", report, changes=changes, request=request)
    return report
