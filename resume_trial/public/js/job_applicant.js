frappe.ui.form.on('Job Applicant', {
    refresh(frm) {
        if (!frm.is_new()) {
            let btn = frm.add_custom_button(__('AI Parse'), function() {
                frappe.call({
                    method: 'resume_trial.frappe_hooks.trigger_resume_parse',
                    args: {
                        docname: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Parsing Resume with AI...'),
                    callback: function(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                            frappe.show_alert({
                                message: __('Resume parsed and screening details autofilled successfully!'),
                                indicator: 'green'
                            });
                        }
                    }
                });
            });

            // Prominently style as a primary button directly next to Shortlist
            btn.addClass('btn-primary');
        }
    }
});
