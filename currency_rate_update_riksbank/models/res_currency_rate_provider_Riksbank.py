# Copyright 2023 Compassion Apps (https://compassion.ch)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import itertools
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import timedelta

import dateutil.parser
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError



class ResCurrencyRateProviderRiksbank(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("Riksbank", "www.riksbank.se")],
        ondelete={"Riksbank": "set default"},
    )
    logger = logging.getLogger(__name__)

    def _get_supported_currencies(self):
        return [
            "NOK",
            "SEK",
            "DKK",
            "CHF",
            "EUR",
        ]


    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "Riksbank":
            return super()._obtain_rates(
                base_currency, currencies, date_from, date_to
            )  # pragma: no cover
        invert_calculation = False
        if base_currency != "SEK":
            invert_calculation = True
            if base_currency not in currencies:
                currencies.append(base_currency)
        content = defaultdict(dict)

        # NOTE: Step in 10 days is selected to reduce memory impact
        step = timedelta(days=10)
        for currency in currencies:
            since = date_from
            until = since + step
            while since <= date_to:
                url = (
                    "https://api-test.riksbank.se/swea/v1/Observations/%(source)s%(target)sPMI/%(from)s/%(to)s"
                ) % {
                    "source": base_currency,
                    "target": currency,
                    "from": str(since),
                    "to": str(min(until, date_to)),
                }
                data = json.loads(self._riksbank_provider_retrieve(url))
                if "error" in data and data["error"]:
                    raise UserError(
                        data["error_description"]
                        if "error_description" in data
                        else "Unknown error"
                    )
                for entry in data:
                     tmp = {}
                     tmp[currency] = entry["value"]
                     content[entry["date"]] = tmp
                since += step
                until += step

        if invert_calculation:
            for k in content.keys():
                base_rate = float(content[k][base_currency])
                for rate in content[k].keys():
                    content[k][rate] = str(float(content[k][rate]) / base_rate)
                content[k]["SEK"] = str(1.0 / base_rate)
        return content

    def _riksbank_provider_retrieve(self, url):
        self.ensure_one()

        with self._riksbank_provider_urlopen(url) as response:
            self._logger.debug(" retrieving rates at"+url)
            content = response.read().decode('utf-8')
        return content

    def _riksbank_provider_urlopen(self, url):
        self.ensure_one()
        request = urllib.request.Request(url)
        return urllib.request.urlopen(request)
