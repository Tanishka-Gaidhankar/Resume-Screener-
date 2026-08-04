frappe.listview_settings['Job Applicant'] = {
    onload(listview) {
        listview.page.add_inner_button(__('AI Parse'), function() {
            let selected_docs = listview.get_checked_items();
            if (!selected_docs || selected_docs.length === 0) {
                frappe.msgprint(__('Please select at least one candidate from the list.'));
                return;
            }

            frappe.confirm(
                __('Are you sure you want to parse resumes for the selected {0} candidate(s)?', [selected_docs.length]),
                function() {
                    let names = selected_docs.map(doc => doc.name);
                    frappe.call({
                        method: 'resume_trial.frappe_hooks.bulk_trigger_resume_parse',
                        args: {
                            docnames: names
                        },
                        freeze: true,
                        freeze_message: __('Parsing Resumes with AI...'),
                        callback: function(r) {
                            if (!r.exc && r.message) {
                                if (listview.clear_checked_items) {
                                    listview.clear_checked_items();
                                }
                                listview.refresh();
                                frappe.show_alert({
                                    message: __(r.message.message || 'Resumes parsed successfully!'),
                                    indicator: 'green'
                                });
                            }
                        }
                    });
                }
            );
        }).addClass('btn-primary');
    }
};
