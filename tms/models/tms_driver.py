# Copyright (C) 2018 - TODAY, Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import re

from lxml import etree

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

DRIVER_LICENSE_TYPES = [
    ("A", "A - Motorcycles"),
    ("B", "B - Automobiles"),
    ("C", "C - Truck"),
    ("D", "D - Bus"),
]
LOCATION_TYPES = [("terrestrial", "Terrestrial")]


class TmsDriver(models.Model):
    _name = "tms.driver"
    _inherit = ["mail.thread"]
    _inherits = {"res.partner": "partner_id"}
    _description = "Model for TMS drivers"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")

    # ------------------------------
    #            Driver
    # ------------------------------

    # Driver - Flags
    is_external = fields.Boolean(string="External Driver")
    is_training = fields.Boolean(string="In Training")
    is_active = fields.Boolean(default=True)

    # Driver - Relations
    vehicles_ids = fields.One2many("fleet.vehicle", "tms_driver_id")
    trips_ids = fields.One2many("tms.order", "driver_id")

    tms_team_id = fields.Many2one("tms.team")
    crew_ids = fields.Many2many(
        "tms.crew",
        "tms_crew_drivers_rel",
        string="Crews",
    )
    stage_id = fields.Many2one(
        "tms.stage",
        string="Stage",
        index=True,
        copy=False,
        default=lambda self: self._default_stage_id(),
        group_expand="_read_group_stage_ids",
    )

    # Driver - Type
    driver_type = fields.Selection(
        string="Type", selection=[("terrestrial", "Terrestrial")]
    )

    # ------------------------------
    #      Driver - Terrestrial
    # ------------------------------

    # TODO: ADD A LICENCE MODEL
    # Terrestrial - Licenses
    driver_license_number = fields.Char()
    driver_license_type = fields.Selection(
        string="License type", selection=DRIVER_LICENSE_TYPES
    )
    driver_license_expiration_date = fields.Date()
    driver_license_file = fields.Binary()

    # Terrestrial - Experience
    distance_traveled = fields.Integer()
    distance_traveled_uom = fields.Selection(
        selection=[("km", "km"), ("mi", "mi")], default="km"
    )
    driving_experience_years = fields.Integer()

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        return self.env["tms.stage"].search(
            [("stage_type", "=", "driver")], order=order
        )

    def _default_stage_id(self):
        stage = self.env["tms.stage"].search(
            [("stage_type", "=", "driver")],
            order="sequence asc",
            limit=1,
        )
        if stage:
            return stage.id

    # Inherited actions from res_partner
    #
    # The driver form inherits ``base.view_partner_form``, so every button that
    # other modules add to the partner form (sales, purchases, opportunities,
    # invoices, employees, ...) ends up on this view. Those buttons expect a
    # ``res.partner`` record, so they are rewritten to run on ``partner_id``.

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            self._delegate_partner_buttons(arch)
        return arch, view

    @api.model
    def _delegate_partner_buttons(self, arch):
        partner_model = self.env["res.partner"]
        delegated = False
        for node in arch.iter("button"):
            btype, name = node.get("type"), node.get("name")
            if not name or node.get("special"):
                continue
            if btype == "object":
                if name == "action_tms_partner_button" or not hasattr(
                    partner_model, name
                ):
                    continue
            elif btype != "action":
                continue
            node.set("args", json.dumps([btype, name]))
            node.set("name", "action_tms_partner_button")
            node.set("type", "object")
            context = node.get("context")
            if context:
                # ``id`` is the driver id here, the partner one is ``partner_id``
                node.set("context", re.sub(r"(?<![\w.'\"])id\b", "partner_id", context))
            delegated = True
        if delegated and not arch.xpath("//field[@name='partner_id']"):
            target = (arch.xpath("//sheet") or [arch])[0]
            target.append(
                etree.Element("field", name="partner_id", invisible="1")
            )

    def action_tms_partner_button(self, button_type, name):
        self.ensure_one()
        partner = self.partner_id
        if button_type == "object":
            return getattr(partner, name)()
        action = self._tms_partner_action(name, partner)
        return action

    @api.model
    def _tms_partner_action(self, name, partner):
        if str(name).isdigit():
            action = self.env["ir.actions.actions"].sudo().browse(int(name))
        else:
            action = self.env.ref(name)
        action = self.env[action.type].browse(action.id)._get_action_dict()
        eval_context = dict(
            self.env["ir.actions.actions"]._get_eval_context(),
            context=dict(self.env.context),
            active_id=partner.id,
            active_ids=partner.ids,
            active_model=partner._name,
            allowed_company_ids=self.env.companies.ids,
            context_today=lambda: fields.Date.context_today(self),
        )
        for key, default in (("context", {}), ("domain", [])):
            value = action.get(key)
            if isinstance(value, str):
                action[key] = safe_eval(value, eval_context) if value else default
        action["context"] = dict(
            action.get("context") or {},
            active_id=partner.id,
            active_ids=partner.ids,
            active_model=partner._name,
        )
        return action

    def create_company(self):
        return self.partner_id.create_company()

    def action_open_employees(self):
        return self.partner_id.action_open_employees()

    def open_commercial_entity(self):
        return self.partner_id.open_commercial_entity()

    def phone_action_blacklist_remove(self):
        return self.partner_id.phone_action_blacklist_remove()

    def mail_action_blacklist_remove(self):
        return self.partner_id.mail_action_blacklist_remove()

    def geo_localize(self):
        return self.partner_id.geo_localize()

    def schedule_meeting(self):
        return self.partner_id.schedule_meeting()
