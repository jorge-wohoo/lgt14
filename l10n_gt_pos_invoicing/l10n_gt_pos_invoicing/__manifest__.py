{
    "name": "L10N GT POS INVOCING",
    "version": "14.0.0.1.0",
    "author": "HomebrewSoft",
    "website": "https://homebrewsoft.dev",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "point_of_sale",
        "account",
        "l10n_gt_edi",
        "base_setup",
        "l10n_gt_infile",
    ],
    "data": [
        "data/res_partner.xml",
        # secutity
        "security/ir.model.access.csv",
        # views
        "views/pos_assets_common.xml",
        "views/pos_order.xml",
        "views/pos_config.xml",
        "views/wizard_add_journals.xml",
        "views/sale_order.xml",
        "views/res_groups.xml",
        "views/account_move.xml",
        # reports
        "reports/account_report_invoice_document.xml",
    ],
    "qweb": [
        "static/src/xml/pos_report.xml",
    ],
}
